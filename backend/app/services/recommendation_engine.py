from __future__ import annotations

from app.models.incident import IncidentRecord


class RecommendationEngine:
    def build_recommendation(self, incident: IncidentRecord, overall_score: float) -> str:
        actions = [
            f"Coordinate with regional responders in {incident.region}.",
            "Verify the incident with at least one additional trusted source.",
            "Prepare a public communication update if the situation escalates.",
        ]
        if overall_score >= 80:
            actions.insert(0, "Activate critical-response coordination and notify senior decision makers.")
        elif overall_score >= 60:
            actions.insert(0, "Increase monitoring and stage response resources near the affected area.")
        return " ".join(actions)


recommendation_engine = RecommendationEngine()
