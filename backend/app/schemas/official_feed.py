from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.incident import IncidentLocationOut, SourceInfoOut


class OfficialFeedPostOut(BaseModel):
    id: str
    source_id: str
    source_name: str
    is_custom: bool
    platform: str
    publisher_name: str
    account_label: str
    account_handle: str
    account_url: str
    post_url: str
    content: str
    signal_tags: list[str] = Field(default_factory=list)
    source_info: SourceInfoOut
    published_at: datetime
    is_safety_relevant: bool
    category: str
    severity: str
    region: str
    location_name: str
    location: IncidentLocationOut
    risk_score: float
    keywords: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    primary_keyword: str | None = None
    ai_signals: list[str] | None = None
    ai_scenario: str | None = None
    ai_severity: str | None = None
    ai_confidence: float | None = None
    ai_is_rumor: bool | None = None
    ai_sentiment: str | None = None
    location_resolution_method: str = "none"
    ai_analysis_status: str = "missing_key"
    ai_location_names: list[str] = Field(default_factory=list)
