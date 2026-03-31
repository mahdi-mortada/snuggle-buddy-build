from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.risk_score import RiskPredictionRecord, RiskScoreRecord


class PredictionEngine:
    def build_predictions(self, scores: list[RiskScoreRecord]) -> list[RiskPredictionRecord]:
        now = datetime.now(UTC)
        horizons = {"24h": 1.03, "48h": 1.05, "7d": 1.08}
        deltas = {"24h": timedelta(hours=24), "48h": timedelta(hours=48), "7d": timedelta(days=7)}
        predictions: list[RiskPredictionRecord] = []
        for score in scores:
            for horizon, multiplier in horizons.items():
                predictions.append(
                    RiskPredictionRecord(
                        region=score.region,
                        horizon=horizon,
                        predicted_score=min(100.0, round(score.overall_score * multiplier, 2)),
                        confidence=max(0.5, round(score.confidence - 0.05, 2)),
                        predicted_for=now + deltas[horizon],
                    )
                )
        return predictions


prediction_engine = PredictionEngine()
