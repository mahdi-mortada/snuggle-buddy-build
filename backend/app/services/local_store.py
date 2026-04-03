from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import get_settings
from app.models.alert import AlertRecord
from app.models.incident import IncidentRecord
from app.models.risk_score import RiskPredictionRecord, RiskScoreRecord
from app.models.user import UserRecord
from app.services.alert_service import alert_service
from app.services.auth_service import hash_password
from app.services.prediction_engine import prediction_engine
from app.services.risk_scoring import risk_scoring_service
from app.services.seed_data import build_seed_admin, build_seed_alerts, build_seed_incidents, build_seed_risk_scores


class LocalStore:
    def __init__(self) -> None:
        settings = get_settings()
        self._path = Path(settings.local_data_file)
        self._state: dict[str, list[dict]] = {"users": [], "incidents": [], "risk_scores": [], "alerts": []}

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        settings = get_settings()
        if self._path.exists():
            self._state = json.loads(self._path.read_text(encoding="utf-8"))
            if settings.storage_mode == "postgres":
                self._normalize_postgres_state()
            if self._state.get("users"):
                return
        admin = build_seed_admin(
            hashed_password=hash_password(settings.admin_password),
            email=settings.admin_email,
            full_name=settings.admin_full_name,
            organization=settings.admin_organization,
        )

        if settings.storage_mode == "postgres":
            incidents: list[IncidentRecord] = []
            risk_scores: list[RiskScoreRecord] = []
            alerts: list[AlertRecord] = []
        else:
            incidents = build_seed_incidents()
            risk_scores = build_seed_risk_scores()
            alerts = build_seed_alerts(risk_scores)

        self._state = {
            "users": [admin.model_dump(mode="json")],
            "incidents": [incident.model_dump(mode="json") for incident in incidents],
            "risk_scores": [risk.model_dump(mode="json") for risk in risk_scores],
            "alerts": [alert.model_dump(mode="json") for alert in alerts],
        }
        self.persist()

    def _normalize_postgres_state(self) -> None:
        incidents = [
            incident
            for incident in self.list_incidents()
            if not (incident.source_id or "").startswith("seed-")
        ]
        self._state["incidents"] = [incident.model_dump(mode="json") for incident in incidents]
        self.recalculate()
        self.persist()

    def persist(self) -> None:
        self._path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def list_users(self) -> list[UserRecord]:
        return [UserRecord.model_validate(row) for row in self._state["users"]]

    def get_user_by_email(self, email: str) -> UserRecord | None:
        return next((row for row in self.list_users() if row.email == email), None)

    def create_user(self, user: UserRecord) -> UserRecord:
        self._state["users"].append(user.model_dump(mode="json"))
        self.persist()
        return user

    def list_incidents(self) -> list[IncidentRecord]:
        return [IncidentRecord.model_validate(row) for row in self._state["incidents"]]

    def get_incident(self, incident_id: str) -> IncidentRecord | None:
        return next((row for row in self.list_incidents() if row.id == incident_id), None)

    def create_incident(self, incident: IncidentRecord) -> IncidentRecord:
        self._state["incidents"].append(incident.model_dump(mode="json"))
        self.recalculate()
        self.persist()
        return incident

    def upsert_incidents(self, incidents: list[IncidentRecord]) -> tuple[int, int]:
        existing = {incident.id: incident for incident in self.list_incidents()}
        inserted = 0
        updated = 0

        for incident in incidents:
            if incident.id in existing:
                updated += 1
            else:
                inserted += 1
            existing[incident.id] = incident

        merged = sorted(
            existing.values(),
            key=lambda incident: incident.created_at,
            reverse=True,
        )
        self._state["incidents"] = [incident.model_dump(mode="json") for incident in merged]
        self.recalculate()
        self.persist()
        return inserted, updated

    def update_incident(self, incident_id: str, updates: dict) -> IncidentRecord:
        """Generic update for any incident fields (used by analyst review)."""
        incidents = self.list_incidents()
        target: IncidentRecord | None = None
        for incident in incidents:
            if incident.id == incident_id:
                for key, value in updates.items():
                    if hasattr(incident, key):
                        setattr(incident, key, value)
                from datetime import UTC, datetime
                incident.updated_at = datetime.now(UTC)
                target = incident
                break
        if target is None:
            raise KeyError(incident_id)
        self._state["incidents"] = [i.model_dump(mode="json") for i in incidents]
        self.persist()
        return target

    def update_incident_status(self, incident_id: str, status: str) -> IncidentRecord:
        incidents = self.list_incidents()
        target: IncidentRecord | None = None
        for incident in incidents:
            if incident.id == incident_id:
                incident.status = status  # type: ignore[assignment]
                incident.updated_at = datetime.now(UTC)
                target = incident
                break
        if target is None:
            raise KeyError(incident_id)
        self._state["incidents"] = [incident.model_dump(mode="json") for incident in incidents]
        self.recalculate()
        self.persist()
        return target

    def list_risk_scores(self) -> list[RiskScoreRecord]:
        return [RiskScoreRecord.model_validate(row) for row in self._state["risk_scores"]]

    def list_alerts(self) -> list[AlertRecord]:
        return [AlertRecord.model_validate(row) for row in self._state["alerts"]]

    def get_alert(self, alert_id: str) -> AlertRecord | None:
        return next((row for row in self.list_alerts() if row.id == alert_id), None)

    def acknowledge_alert(self, alert_id: str, user_id: str) -> AlertRecord:
        alerts = self.list_alerts()
        target: AlertRecord | None = None
        for alert in alerts:
            if alert.id == alert_id:
                alert.is_acknowledged = True
                alert.acknowledged_by = user_id
                alert.acknowledged_at = datetime.now(UTC)
                target = alert
                break
        if target is None:
            raise KeyError(alert_id)
        self._state["alerts"] = [alert.model_dump(mode="json") for alert in alerts]
        self.persist()
        return target

    def recalculate(self) -> tuple[list[RiskScoreRecord], list[AlertRecord]]:
        incidents = self.list_incidents()
        risk_scores = risk_scoring_service.calculate(incidents)
        alerts = alert_service.generate_alerts(incidents, risk_scores)
        self._state["risk_scores"] = [risk.model_dump(mode="json") for risk in risk_scores]
        self._state["alerts"] = [alert.model_dump(mode="json") for alert in alerts]
        return risk_scores, alerts

    def risk_history(self, region: str | None = None, points: int = 7) -> list[RiskScoreRecord]:
        base_scores = self.list_risk_scores()
        history: list[RiskScoreRecord] = []
        for score in base_scores:
            if region and score.region != region:
                continue
            for offset in range(points):
                delta = points - offset
                history.append(
                    RiskScoreRecord(
                        **{
                            **score.model_dump(),
                            "id": f"{score.id}-history-{offset}",
                            "overall_score": max(0.0, round(score.overall_score - delta * 1.7, 2)),
                            "calculated_at": datetime.now(UTC) - timedelta(days=delta),
                        }
                    )
                )
        return history

    def predictions(self, region: str | None = None) -> list[RiskPredictionRecord]:
        scores = self.list_risk_scores()
        if region:
            scores = [score for score in scores if score.region == region]
        return prediction_engine.build_predictions(scores)

    def dashboard_trends(self) -> list[dict[str, object]]:
        now = datetime.now(UTC)
        current_scores = {score.region: score for score in self.list_risk_scores()}
        incidents = self.list_incidents()
        output: list[dict[str, object]] = []
        for hour_offset in range(24):
            point_time = now - timedelta(hours=23 - hour_offset)
            relevant = [incident for incident in incidents if incident.created_at <= point_time]
            avg_risk = round(sum(score.overall_score for score in current_scores.values()) / max(len(current_scores), 1), 2)
            sentiment = round(sum(incident.sentiment_score for incident in relevant) / max(len(relevant), 1), 2) if relevant else 0.0
            output.append(
                {
                    "time": point_time.isoformat(),
                    "incidents": len(relevant),
                    "risk_score": avg_risk,
                    "sentiment": sentiment,
                }
            )
        return output

    def dashboard_hotspots(self) -> list[dict[str, object]]:
        by_region: dict[str, list[IncidentRecord]] = {}
        for incident in self.list_incidents():
            by_region.setdefault(incident.region, []).append(incident)
        hotspots = []
        for region, region_incidents in by_region.items():
            avg_risk = round(sum(incident.risk_score for incident in region_incidents) / max(len(region_incidents), 1), 2)
            hotspots.append(
                {
                    "region": region,
                    "incident_count": len(region_incidents),
                    "risk_level": avg_risk,
                    "coordinates": {
                        "lat": round(sum(incident.location.lat for incident in region_incidents) / len(region_incidents), 4),
                        "lng": round(sum(incident.location.lng for incident in region_incidents) / len(region_incidents), 4),
                    },
                }
            )
        hotspots.sort(key=lambda item: (item["risk_level"], item["incident_count"]), reverse=True)
        return hotspots[:10]

    def snapshot(self) -> dict[str, list[dict]]:
        return deepcopy(self._state)


local_store = LocalStore()
