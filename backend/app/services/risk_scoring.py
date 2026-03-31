from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.models.incident import IncidentRecord
from app.models.risk_score import RiskScoreRecord
from app.services.feature_engineering import feature_engineering_service


class RiskScoringService:
    def __init__(self) -> None:
        self.weights: dict[str, float] = {
            "sentiment_component": 0.25,
            "volume_component": 0.25,
            "keyword_component": 0.20,
            "behavior_component": 0.15,
            "geospatial_component": 0.15,
        }

    def calculate(self, incidents: list[IncidentRecord]) -> list[RiskScoreRecord]:
        features_by_region = feature_engineering_service.build_region_features(incidents)
        calculated_at = datetime.now(UTC)
        results: list[RiskScoreRecord] = []
        for region, features in sorted(features_by_region.items()):
            overall = sum(features[name] * weight for name, weight in self.weights.items())
            results.append(
                RiskScoreRecord(
                    id=str(uuid4()),
                    region=region,
                    overall_score=round(min(100.0, overall), 2),
                    sentiment_component=round(features["sentiment_component"], 2),
                    volume_component=round(features["volume_component"], 2),
                    keyword_component=round(features["keyword_component"], 2),
                    behavior_component=round(features["behavior_component"], 2),
                    geospatial_component=round(features["geospatial_component"], 2),
                    confidence=0.78,
                    calculated_at=calculated_at,
                )
            )
        return results


risk_scoring_service = RiskScoringService()
