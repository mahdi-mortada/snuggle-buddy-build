from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AlertOut(BaseModel):
    id: str
    risk_score_id: str | None = None
    incident_id: str | None = None
    alert_type: str
    severity: str
    title: str
    message: str
    recommendation: str
    region: str
    is_acknowledged: bool
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    notification_channels: list[str]
    linked_incidents: list[str]
    created_at: datetime


class AlertAcknowledgeRequest(BaseModel):
    acknowledge: bool = True


class AlertStatsOut(BaseModel):
    total: int
    acknowledged: int
    by_severity: dict[str, int]
    average_response_minutes: float
