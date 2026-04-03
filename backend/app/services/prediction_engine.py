"""Prediction Engine — Section 7.1.

Uses Facebook Prophet for per-region time-series forecasting.
Forecast horizons: 24h, 48h, 7d.
Falls back to simple trend extrapolation when Prophet is unavailable or
training data is insufficient (<30 days).

Retrained daily at midnight via Celery beat.
"""
from __future__ import annotations

import logging
import pickle
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

from app.models.risk_score import RiskPredictionRecord, RiskScoreRecord

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parents[2] / "ml-pipeline" / "models" / "prophet"
HORIZONS = {
    "24h": timedelta(hours=24),
    "48h": timedelta(hours=48),
    "7d": timedelta(days=7),
}


class PredictionEngine:
    """Prophet-based risk score forecasting per Lebanon region."""

    def __init__(self) -> None:
        # region → trained Prophet model
        self._models: dict[str, object] = {}
        self._trained_at: Optional[datetime] = None

    def build_predictions(self, scores: list[RiskScoreRecord]) -> list[RiskPredictionRecord]:
        """Sync fallback used by LocalStore.predictions() — simple trend extrapolation."""
        now = datetime.now(UTC)
        multipliers = {"24h": 1.03, "48h": 1.05, "7d": 1.08}
        predictions: list[RiskPredictionRecord] = []
        for score in scores:
            for horizon, mult in multipliers.items():
                delta = HORIZONS[horizon]
                predicted = min(100.0, round(score.overall_score * mult, 2))
                predictions.append(
                    RiskPredictionRecord(
                        region=score.region,
                        horizon=horizon,
                        predicted_score=predicted,
                        lower_bound=max(0.0, predicted - 10),
                        upper_bound=min(100.0, predicted + 10),
                        confidence=max(0.4, round(score.confidence - 0.05, 2)),
                        escalation_probability=0.0,
                        predicted_for=now + delta,
                    )
                )
        return predictions

    async def get_predictions(
        self,
        region: Optional[str] = None,
        horizon: Optional[str] = None,
    ) -> list[dict]:
        """
        Get forecasts using trained Prophet models.
        Returns list of dicts compatible with RiskPredictionOut schema.
        """
        results = []
        now = datetime.now(UTC)

        horizons = {horizon: HORIZONS[horizon]} if horizon and horizon in HORIZONS else HORIZONS

        from app.services.local_store import local_store

        scores = local_store.list_risk_scores()
        target_regions = [region] if region else list({s.region for s in scores})

        for reg in target_regions:
            region_model = self._models.get(reg)
            region_scores = [s for s in scores if s.region == reg]

            if region_model and region_scores:
                # Proper Prophet forecast
                try:
                    for hz, delta in horizons.items():
                        pred = self._forecast_with_prophet(region_model, now + delta)
                        results.append({
                            "region": reg,
                            "horizon": hz,
                            "predicted_score": round(pred["yhat"], 2),
                            "lower_bound": round(max(0.0, pred["yhat_lower"]), 2),
                            "upper_bound": round(min(100.0, pred["yhat_upper"]), 2),
                            "confidence": 0.82,
                            "escalation_probability": await self._escalation_probability(reg),
                            "predicted_for": (now + delta).isoformat(),
                            "model_version": "prophet-v1",
                        })
                    continue
                except Exception as exc:
                    logger.debug("Prophet forecast failed for %s: %s", reg, exc)

            # Fallback: trend extrapolation from local store
            if region_scores:
                score = region_scores[0]
                for hz, delta in horizons.items():
                    mult = {"24h": 1.03, "48h": 1.05, "7d": 1.08}[hz]
                    predicted = round(min(100.0, score.overall_score * mult), 2)
                    results.append({
                        "region": reg,
                        "horizon": hz,
                        "predicted_score": predicted,
                        "lower_bound": max(0.0, predicted - 10),
                        "upper_bound": min(100.0, predicted + 10),
                        "confidence": max(0.4, score.confidence - 0.05),
                        "escalation_probability": 0.0,
                        "predicted_for": (now + delta).isoformat(),
                        "model_version": "fallback-extrapolation",
                    })

        return results

    def _forecast_with_prophet(self, model, target_dt: datetime) -> dict:
        """Run Prophet inference for a single future timestamp."""
        import pandas as pd

        future = pd.DataFrame({"ds": [target_dt]})
        forecast = model.predict(future)
        row = forecast.iloc[0]
        return {
            "yhat": float(row["yhat"]),
            "yhat_lower": float(row["yhat_lower"]),
            "yhat_upper": float(row["yhat_upper"]),
        }

    async def train_region(self, region: str, historical_scores: list[dict]) -> bool:
        """Train Prophet model for a single region on historical risk scores."""
        if len(historical_scores) < 10:
            logger.info("Not enough data to train Prophet for %s (%d points)", region, len(historical_scores))
            return False

        try:
            from prophet import Prophet
            import pandas as pd

            df = pd.DataFrame([
                {"ds": s["calculated_at"], "y": s["overall_score"]}
                for s in historical_scores
            ])
            df["ds"] = pd.to_datetime(df["ds"])
            df = df.sort_values("ds").dropna()

            model = Prophet(
                yearly_seasonality=False,
                weekly_seasonality=True,
                daily_seasonality=True,
                changepoint_prior_scale=0.05,
            )
            model.fit(df)
            self._models[region] = model
            self._trained_at = datetime.now(UTC)

            # Persist model to disk
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            model_path = MODELS_DIR / f"{region.replace(' ', '_').lower()}.pkl"
            with open(model_path, "wb") as f:
                pickle.dump(model, f)

            logger.info("Prophet model trained for region '%s' (%d points)", region, len(df))
            return True
        except Exception as exc:
            logger.error("Prophet training failed for %s: %s", region, exc)
            return False

    async def train_all_regions(self) -> int:
        """Train Prophet for all regions with sufficient history. Returns count trained."""
        from app.services.local_store import local_store

        scores = local_store.list_risk_scores()
        regions = list({s.region for s in scores})
        trained_count = 0

        for region in regions:
            # Build historical data from risk_history
            history = local_store.risk_history(region=region, points=30)
            historical_dicts = [s.model_dump(mode="json") for s in history]
            if await self.train_region(region, historical_dicts):
                trained_count += 1

        return trained_count

    def load_models(self) -> int:
        """Load all persisted Prophet models from disk."""
        if not MODELS_DIR.exists():
            return 0
        count = 0
        for model_file in MODELS_DIR.glob("*.pkl"):
            try:
                with open(model_file, "rb") as f:
                    model = pickle.load(f)
                region = model_file.stem.replace("_", " ").title()
                self._models[region] = model
                count += 1
            except Exception as exc:
                logger.warning("Failed to load Prophet model %s: %s", model_file.name, exc)
        if count:
            logger.info("Loaded %d Prophet models from disk", count)
        return count

    async def _escalation_probability(self, region: str) -> float:
        """Get escalation probability from XGBoost model if available."""
        try:
            from app.services.escalation_model import escalation_model
            from app.services.local_store import local_store

            if not escalation_model.is_trained:
                return 0.0
            scores = [s for s in local_store.list_risk_scores() if s.region == region]
            if scores:
                return escalation_model.predict_probability(scores[0])
        except Exception:
            pass
        return 0.0


prediction_engine = PredictionEngine()
# Load saved models on import
prediction_engine.load_models()
