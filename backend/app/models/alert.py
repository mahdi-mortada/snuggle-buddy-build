from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


AlertSeverity = Literal["info", "warning", "critical", "emergency"]


class AlertRecord(BaseModel):
    id: str
    risk_score_id: str | None = None
    incident_id: str | None = None
    alert_type: str
    severity: AlertSeverity
    title: str
    message: str
    recommendation: str
    region: str
    is_acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    notification_channels: list[str] = Field(default_factory=lambda: ["dashboard"])
    linked_incidents: list[str] = Field(default_factory=list)
    created_at: datetime
