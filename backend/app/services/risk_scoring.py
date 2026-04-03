"""Risk Scoring Service — Section 6.1.

Computes composite risk score per region using 5-component formula:
  overall = 0.25*sentiment + 0.25*volume + 0.20*keyword + 0.15*behavior + 0.15*geospatial

Weights are loaded from Redis (configurable at runtime) and fall back to defaults.
Risk scores are cached in Redis (TTL 5 min) and stored in risk_scores table.
Risk recalculation runs every 15 minutes via Celery.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Optional
from uuid import uuid4

from app.models.incident import IncidentRecord
from app.models.risk_score import RiskScoreRecord
from app.services.feature_engineering import feature_engineering_service

logger = logging.getLogger(__name__)

MODEL_VERSION = "risk-scoring-v1.0"


class RiskScoringService:
    """
    Composite risk scoring with Redis-backed configurable weights.
    """

    _DEFAULT_WEIGHTS = {
        "sentiment": 0.25,
        "volume": 0.25,
        "keyword": 0.20,
        "behavior": 0.15,
        "geospatial": 0.15,
    }

    def calculate(self, incidents: list[IncidentRecord]) -> list[RiskScoreRecord]:
        """
        Synchronous version for use by LocalStore and Celery tasks.
        Loads weights from Redis if connected, else uses defaults.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context — can't run sync nested
                weights = self._DEFAULT_WEIGHTS
            else:
                weights = loop.run_until_complete(self._get_weights())
        except Exception:
            weights = self._DEFAULT_WEIGHTS

        return self._compute(incidents, weights)

    async def calculate_async(self, incidents: list[IncidentRecord]) -> list[RiskScoreRecord]:
        """Async version that loads weights from Redis."""
        weights = await self._get_weights()
        scores = self._compute(incidents, weights)

        # Cache each region's score in Redis
        try:
            from app.db.redis import redis_client
            for score in scores:
                await redis_client.cache_risk_score(
                    score.region,
                    score.model_dump(mode="json"),
                    ttl=300,
                )
        except Exception as exc:
            logger.debug("Redis cache update failed: %s", exc)

        return scores

    async def recalculate(self, region: Optional[str] = None) -> list[dict]:
        """
        Full async recalculation triggered by API or Celery.
        Returns list of dicts for API response.
        """
        from app.services.local_store import local_store

        incidents = local_store.list_incidents()
        if region:
            incidents = [i for i in incidents if i.region.lower() == region.lower()]

        scores = await self.calculate_async(incidents)
        return [s.model_dump(mode="json") for s in scores]

    def _compute(
        self,
        incidents: list[IncidentRecord],
        weights: dict[str, float],
    ) -> list[RiskScoreRecord]:
        """Core computation: features → weighted sum → RiskScoreRecord list."""
        features_by_region = feature_engineering_service.build_region_features(incidents)
        calculated_at = datetime.now(UTC)
        results: list[RiskScoreRecord] = []

        # Normalize weights to sum to 1.0
        total_weight = sum(weights.values())
        if total_weight <= 0:
            weights = self._DEFAULT_WEIGHTS
            total_weight = 1.0
        normalized = {k: v / total_weight for k, v in weights.items()}

        for region, features in sorted(features_by_region.items()):
            s = features["sentiment_component"]
            v = features["volume_component"]
            k = features["keyword_component"]
            b = features["behavior_component"]
            g = features["geospatial_component"]

            overall = (
                normalized["sentiment"] * s
                + normalized["volume"] * v
                + normalized["keyword"] * k
                + normalized["behavior"] * b
                + normalized["geospatial"] * g
            )

            # Confidence: based on incident count — more incidents = more confident
            region_count = sum(1 for i in incidents if i.region == region)
            confidence = min(0.99, 0.5 + (region_count / 20) * 0.49)

            results.append(
                RiskScoreRecord(
                    id=str(uuid4()),
                    region=region,
                    overall_score=round(min(100.0, max(0.0, overall)), 2),
                    sentiment_component=round(s, 2),
                    volume_component=round(v, 2),
                    keyword_component=round(k, 2),
                    behavior_component=round(b, 2),
                    geospatial_component=round(g, 2),
                    confidence=round(confidence, 3),
                    model_version=MODEL_VERSION,
                    calculated_at=calculated_at,
                )
            )

        logger.info(
            "Risk recalculation complete: %d regions, weights=%s",
            len(results),
            {k: round(v, 3) for k, v in normalized.items()},
        )
        return results

    async def _get_weights(self) -> dict[str, float]:
        """Load weights from Redis, fall back to defaults."""
        try:
            from app.db.redis import redis_client
            return await redis_client.get_risk_weights()
        except Exception:
            return self._DEFAULT_WEIGHTS


risk_scoring_service = RiskScoringService()
