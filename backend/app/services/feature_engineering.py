from __future__ import annotations

from collections import defaultdict

from app.models.incident import IncidentRecord


class FeatureEngineeringService:
    def build_region_features(self, incidents: list[IncidentRecord]) -> dict[str, dict[str, float]]:
        by_region: dict[str, list[IncidentRecord]] = defaultdict(list)
        for incident in incidents:
            by_region[incident.region].append(incident)

        output: dict[str, dict[str, float]] = {}
        for region, region_incidents in by_region.items():
            volume = float(len(region_incidents))
            sentiment = sum(abs(incident.sentiment_score) for incident in region_incidents) / max(len(region_incidents), 1)
            keyword = sum(len(incident.keywords) for incident in region_incidents) / max(len(region_incidents), 1)
            behavior = sum(1 for incident in region_incidents if incident.status in {"new", "escalated"}) / max(len(region_incidents), 1)
            geospatial = len({(incident.location.lat, incident.location.lng) for incident in region_incidents}) / max(len(region_incidents), 1)

            output[region] = {
                "sentiment_component": min(100.0, sentiment * 100),
                "volume_component": min(100.0, volume * 16),
                "keyword_component": min(100.0, keyword * 22),
                "behavior_component": min(100.0, behavior * 100),
                "geospatial_component": min(100.0, geospatial * 100),
            }
        return output


feature_engineering_service = FeatureEngineeringService()
