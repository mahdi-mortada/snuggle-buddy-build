from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.models.alert import AlertRecord
from app.models.incident import IncidentRecord
from app.models.risk_score import RiskScoreRecord
from app.services.recommendation_engine import recommendation_engine


class AlertService:
    def generate_alerts(self, incidents: list[IncidentRecord], risk_scores: list[RiskScoreRecord]) -> list[AlertRecord]:
        risk_lookup = {risk.region: risk for risk in risk_scores}
        alerts: list[AlertRecord] = []
        for incident in incidents:
            risk = risk_lookup.get(incident.region)
            if not risk:
                continue
            severity = self._severity_from_score(risk.overall_score)
            if severity is None:
                continue
            alerts.append(
                AlertRecord(
                    id=str(uuid4()),
                    risk_score_id=risk.id,
                    incident_id=incident.id,
                    alert_type="threshold_breach" if risk.overall_score >= 60 else "trend",
                    severity=severity,
                    title=f"{incident.region} risk update",
                    message=f"{incident.title} is contributing to a {risk.overall_score}/100 risk score in {incident.region}.",
                    recommendation=recommendation_engine.build_recommendation(incident, risk.overall_score),
                    region=incident.region,
                    linked_incidents=[incident.id],
                    created_at=datetime.now(UTC),
                )
            )
        deduped: dict[tuple[str, str], AlertRecord] = {}
        for alert in alerts:
            deduped[(alert.region, alert.severity)] = alert
        return list(deduped.values())

    def _severity_from_score(self, overall_score: float) -> str | None:
        if overall_score > 90:
            return "emergency"
        if overall_score > 80:
            return "critical"
        if overall_score > 60:
            return "warning"
        if overall_score > 40:
            return "info"
        return None


alert_service = AlertService()
