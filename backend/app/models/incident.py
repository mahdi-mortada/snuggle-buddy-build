from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


IncidentSource = Literal["social_media", "news", "web_scraping", "manual", "sensor", "crowdsource"]
IncidentCategory = Literal["violence", "protest", "natural_disaster", "infrastructure", "health", "terrorism", "cyber", "other"]
IncidentSeverity = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal["new", "processing", "analyzed", "escalated", "resolved", "false_alarm"]
SourceType = Literal["tv", "newspaper", "news_agency", "social_media", "government", "ngo", "sensor"]
CredibilityLevel = Literal["verified", "high", "moderate", "low", "unverified"]


class SourceInfoRecord(BaseModel):
    name: str
    type: SourceType
    credibility: CredibilityLevel
    credibility_score: float = Field(alias="credibilityScore")
    logo_initials: str = Field(alias="logoInitials")
    url: str | None = None
    verified_by: list[str] = Field(default_factory=list, alias="verifiedBy")

    model_config = {"populate_by_name": True}


class IncidentLocation(BaseModel):
    lat: float
    lng: float


class IncidentRecord(BaseModel):
    id: str
    source: IncidentSource
    source_id: str | None = None
    title: str
    description: str
    raw_text: str
    category: IncidentCategory
    severity: IncidentSeverity
    location: IncidentLocation
    location_name: str
    region: str
    country: str = "Lebanon"
    sentiment_score: float
    risk_score: float
    entities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    language: str = "en"
    is_verified: bool = False
    status: IncidentStatus = "new"
    metadata: dict[str, str] = Field(default_factory=dict)
    source_info: SourceInfoRecord
    source_url: str | None = None
    created_at: datetime
    updated_at: datetime
