"""Feature Engineering Service — Section 5.

Computes per-region features for the risk scoring model:
  - sentiment_component: mean sentiment + velocity
  - volume_component: z-score relative to historical baseline
  - keyword_component: max keyword threat score in last 6h
  - behavior_component: abnormal posting patterns, engagement spikes
  - geospatial_component: incident density / clustering
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Optional

from app.models.incident import IncidentRecord

logger = logging.getLogger(__name__)


class FeatureEngineeringService:
    """Compute per-region feature vectors from incident lists."""

    def build_region_features(
        self,
        incidents: list[IncidentRecord],
        now: Optional[datetime] = None,
    ) -> dict[str, dict[str, float]]:
        """
        Build feature vectors for all regions present in incidents.

        Returns:
            { region: { sentiment_component, volume_component, keyword_component,
                        behavior_component, geospatial_component } }
        """
        if now is None:
            now = datetime.now(UTC)

        by_region: dict[str, list[IncidentRecord]] = defaultdict(list)
        for incident in incidents:
            by_region[incident.region].append(incident)

        output: dict[str, dict[str, float]] = {}
        for region, region_incidents in by_region.items():
            if region == "unknown":
                continue
            output[region] = self._compute_features(region_incidents, region, now)
        return output

    def _compute_features(
        self,
        incidents: list[IncidentRecord],
        region: str,
        now: datetime,
    ) -> dict[str, float]:
        """Compute all 5 feature components for a single region."""
        return {
            "sentiment_component": self._sentiment_component(incidents, now),
            "volume_component": self._volume_component(incidents, now),
            "keyword_component": self._keyword_component(incidents, now),
            "behavior_component": self._behavior_component(incidents, now),
            "geospatial_component": self._geospatial_component(incidents),
        }

    # ── Component 1: Sentiment ────────────────────────────────────────────────

    def _sentiment_component(self, incidents: list[IncidentRecord], now: datetime) -> float:
        """
        Score based on:
          - Mean sentiment of recent incidents (negative = higher score)
          - Sentiment velocity: rate of change over 1h, 6h, 24h
        Range: 0-100
        """
        recent_24h = self._in_window(incidents, now, hours=24)
        if not recent_24h:
            return 0.0

        # Mean sentiment (negative → more dangerous → higher risk component)
        mean_sentiment = sum(i.sentiment_score for i in recent_24h) / len(recent_24h)
        # Convert from [-1, 1] to [0, 100] where -1 (very negative) = 100
        base_score = ((-mean_sentiment) + 1) / 2 * 100

        # Sentiment velocity (is sentiment getting worse quickly?)
        velocity_score = self._sentiment_velocity(incidents, now)

        return round(min(100.0, max(0.0, base_score * 0.7 + velocity_score * 0.3)), 2)

    def _sentiment_velocity(self, incidents: list[IncidentRecord], now: datetime) -> float:
        """Rate of sentiment deterioration. Higher = faster deterioration."""
        recent_1h = self._in_window(incidents, now, hours=1)
        recent_6h = self._in_window(incidents, now, hours=6)

        if not recent_6h:
            return 0.0

        mean_1h = sum(i.sentiment_score for i in recent_1h) / max(len(recent_1h), 1) if recent_1h else 0.0
        mean_6h = sum(i.sentiment_score for i in recent_6h) / len(recent_6h)

        # Velocity: how much has sentiment dropped from 6h ago to now?
        delta = mean_6h - mean_1h  # positive = getting worse (more negative)
        return min(100.0, max(0.0, delta * 100))

    # ── Component 2: Volume ───────────────────────────────────────────────────

    def _volume_component(self, incidents: list[IncidentRecord], now: datetime) -> float:
        """
        Z-score of incident volume in last 24h relative to historical mean.
        Anomalous spike (z > 2) → high score.
        Range: 0-100
        """
        # Compute volume in multiple 24h windows going back 30 days
        daily_counts: list[float] = []
        for day_offset in range(1, 31):
            window_start = now - timedelta(days=day_offset + 1)
            window_end = now - timedelta(days=day_offset)
            count = sum(
                1 for i in incidents
                if window_start <= self._ensure_utc(i.created_at) < window_end
            )
            daily_counts.append(float(count))

        current_24h = float(len(self._in_window(incidents, now, hours=24)))

        if not daily_counts or all(c == 0 for c in daily_counts):
            # No history — use raw count with soft scaling
            return min(100.0, current_24h * 8.0)

        mean = sum(daily_counts) / len(daily_counts)
        variance = sum((c - mean) ** 2 for c in daily_counts) / len(daily_counts)
        std = math.sqrt(variance) if variance > 0 else 1.0

        z_score = (current_24h - mean) / std
        # Map z-score to 0-100: z=0 → 20, z=2 → 60, z=4+ → 100
        score = 20 + max(0.0, z_score) * 20
        return round(min(100.0, max(0.0, score)), 2)

    # ── Component 3: Keyword ──────────────────────────────────────────────────

    def _keyword_component(self, incidents: list[IncidentRecord], now: datetime) -> float:
        """
        Max keyword threat score among incidents in last 6h.
        Range: 0-100
        """
        recent_6h = self._in_window(incidents, now, hours=6)
        if not recent_6h:
            return 0.0

        # Use incident's keyword list length as proxy for threat keyword score
        # (Real score comes from NLP pipeline keyword_score field if stored in metadata)
        max_score = 0.0
        for incident in recent_6h:
            # Try to get stored keyword_score from metadata
            stored_kw_score = incident.metadata.get("keyword_score", None)
            if stored_kw_score is not None:
                max_score = max(max_score, float(stored_kw_score))
            else:
                # Proxy: high-severity incidents get higher keyword score
                severity_map = {"low": 10, "medium": 30, "high": 60, "critical": 90}
                proxy = float(severity_map.get(incident.severity, 10))
                max_score = max(max_score, proxy)

        return round(min(100.0, max_score), 2)

    # ── Component 4: Behavior ─────────────────────────────────────────────────

    def _behavior_component(self, incidents: list[IncidentRecord], now: datetime) -> float:
        """
        Detect abnormal patterns:
          - Same source posting repeatedly (crowdsource spam)
          - High proportion of unverified/new incidents
          - Sudden burst (many incidents in < 30 min)
        Range: 0-100
        """
        recent_1h = self._in_window(incidents, now, hours=1)
        if not recent_1h:
            return 0.0

        score = 0.0

        # Burst detection: > 5 incidents in 30 minutes
        very_recent = self._in_window(incidents, now, minutes=30)
        if len(very_recent) >= 5:
            score += min(40.0, len(very_recent) * 5.0)

        # Proportion of unverified escalated incidents
        escalated = sum(1 for i in recent_1h if i.status == "escalated")
        score += min(30.0, escalated / max(len(recent_1h), 1) * 100)

        # Source diversity: many different sources = more credible (lower behavior score)
        sources = {i.source for i in recent_1h}
        if len(sources) == 1 and len(recent_1h) > 3:
            score += 20.0  # single-source spam signal

        return round(min(100.0, score), 2)

    # ── Component 5: Geospatial ───────────────────────────────────────────────

    def _geospatial_component(self, incidents: list[IncidentRecord]) -> float:
        """
        Score based on geographic clustering density.
        Tightly clustered incidents in a small area → high geospatial score.
        Range: 0-100
        """
        if len(incidents) < 2:
            return min(100.0, len(incidents) * 15.0)

        # Compute bounding box area (proxy for clustering)
        lats = [i.location.lat for i in incidents]
        lngs = [i.location.lng for i in incidents]
        lat_range = max(lats) - min(lats)
        lng_range = max(lngs) - min(lngs)

        # 1 degree ≈ 111km; small area + many incidents = high density
        area_km2 = max(0.01, lat_range * 111 * lng_range * 111)
        density = len(incidents) / area_km2

        # Normalize: density of 1 incident/km² → 50; 2+/km² → 100
        score = min(100.0, density * 50)
        return round(score, 2)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _in_window(
        self,
        incidents: list[IncidentRecord],
        now: datetime,
        hours: int = 0,
        minutes: int = 0,
    ) -> list[IncidentRecord]:
        cutoff = now - timedelta(hours=hours, minutes=minutes)
        return [i for i in incidents if self._ensure_utc(i.created_at) >= cutoff]

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    def build_feature_vector(self, features: dict[str, float]) -> list[float]:
        """Convert features dict to ordered list for ML models."""
        return [
            features.get("sentiment_component", 0.0) / 100,
            features.get("volume_component", 0.0) / 100,
            features.get("keyword_component", 0.0) / 100,
            features.get("behavior_component", 0.0) / 100,
            features.get("geospatial_component", 0.0) / 100,
        ]


feature_engineering_service = FeatureEngineeringService()
