"""Escalation Probability Model — Section 7.2.

Binary classifier: Will risk escalate above threshold in next 24h?
Algorithm: XGBoost GradientBoostingClassifier
Features: [current_risk, risk_velocity_24h, sentiment_trend, volume_trend,
           day_of_week, historical_escalation_rate]
Tracked with MLflow.
"""
from __future__ import annotations

import logging
import pickle
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

from app.models.risk_score import RiskScoreRecord

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parents[2] / "ml-pipeline" / "models" / "escalation_model.pkl"
ESCALATION_THRESHOLD = 70.0


class EscalationModel:
    """XGBoost escalation probability classifier."""

    def __init__(self) -> None:
        self._model = None
        self._trained_at: Optional[datetime] = None
        self._mlflow_run_id: Optional[str] = None

    @property
    def is_trained(self) -> bool:
        return self._model is not None

    def load(self) -> bool:
        if MODEL_PATH.exists():
            try:
                with open(MODEL_PATH, "rb") as f:
                    saved = pickle.load(f)
                self._model = saved["model"]
                self._trained_at = saved.get("trained_at")
                logger.info("Escalation model loaded (trained %s)", self._trained_at)
                return True
            except Exception as exc:
                logger.warning("Failed to load escalation model: %s", exc)
        return False

    def _build_features(self, score: RiskScoreRecord) -> list[float]:
        """Extract feature vector from a risk score record."""
        now = datetime.now(UTC)
        return [
            score.overall_score / 100.0,
            score.sentiment_component / 100.0,
            score.volume_component / 100.0,
            score.keyword_component / 100.0,
            score.behavior_component / 100.0,
            score.geospatial_component / 100.0,
            float(now.weekday()) / 6.0,  # 0=Mon, 6=Sun
            float(now.hour) / 23.0,
        ]

    def predict_probability(self, score: RiskScoreRecord) -> float:
        """Return probability [0, 1] of escalation in next 24h."""
        if not self._model:
            # Heuristic fallback
            return min(1.0, score.overall_score / 100.0 * 0.8)

        try:
            import numpy as np
            features = np.array([self._build_features(score)])
            proba = self._model.predict_proba(features)[0][1]
            return round(float(proba), 4)
        except Exception as exc:
            logger.debug("Escalation prediction failed: %s", exc)
            return 0.0

    async def train(self, training_data: list[dict]) -> bool:
        """
        Train on historical risk score data.

        training_data: list of dicts with keys:
          overall_score, sentiment_component, volume_component, keyword_component,
          behavior_component, geospatial_component, calculated_at,
          escalated (bool — whether risk went above threshold within 24h)
        """
        if len(training_data) < 20:
            logger.warning("Not enough samples for escalation training (%d)", len(training_data))
            return False

        try:
            import mlflow
            import numpy as np
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.metrics import classification_report, roc_auc_score
            from sklearn.model_selection import train_test_split

            from app.config import get_settings
            settings = get_settings()

            X = []
            y = []
            for row in training_data:
                score_record = RiskScoreRecord(**row)
                X.append(self._build_features(score_record))
                y.append(1 if row.get("escalated", False) else 0)

            X_arr = np.array(X)
            y_arr = np.array(y)

            X_train, X_test, y_train, y_test = train_test_split(
                X_arr, y_arr, test_size=0.2, random_state=42, stratify=y_arr
            )

            model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=4,
                random_state=42,
            )

            # MLflow tracking
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            mlflow.set_experiment(settings.mlflow_escalation_experiment)

            with mlflow.start_run() as run:
                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)
                y_proba = model.predict_proba(X_test)[:, 1]

                report = classification_report(y_test, y_pred, output_dict=True)
                auc = roc_auc_score(y_test, y_proba) if len(set(y_test)) > 1 else 0.5

                mlflow.log_params({
                    "n_estimators": 100,
                    "learning_rate": 0.1,
                    "max_depth": 4,
                    "training_samples": len(X_train),
                })
                mlflow.log_metrics({
                    "accuracy": report.get("accuracy", 0),
                    "auc": auc,
                    "f1_macro": report.get("macro avg", {}).get("f1-score", 0),
                })
                mlflow.sklearn.log_model(model, "escalation_model")
                self._mlflow_run_id = run.info.run_id

            self._model = model
            self._trained_at = datetime.now(UTC)

            MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(MODEL_PATH, "wb") as f:
                pickle.dump({"model": self._model, "trained_at": self._trained_at}, f)

            logger.info("Escalation model trained: AUC=%.3f, samples=%d", auc, len(X))
            return True
        except Exception as exc:
            logger.error("Escalation model training failed: %s", exc)
            return False


escalation_model = EscalationModel()
escalation_model.load()
