from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


IncidentSource = Literal["social_media", "news", "web_scraping", "manual", "sensor", "crowdsource"]
# armed_conflict added per blueprint Section 0.4.2; maps "conflict" → "armed_conflict"
IncidentCategory = Literal[
    "violence", "protest", "natural_disaster", "infrastructure",
    "health", "terrorism", "cyber", "armed_conflict", "other"
]
IncidentSeverity = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal["new", "processing", "analyzed", "escalated", "resolved", "false_alarm"]
VerificationStatus = Literal["unverified", "reviewed", "confirmed", "rejected"]
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
    source_url: str | None = None
    title: str
    description: str
    raw_text: str
    processed_text: str | None = None
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
    processing_status: str = "pending"

    # Data integrity fields (Section 0.4.3)
    verification_status: VerificationStatus = "unverified"
    confidence_score: Optional[float] = None

    # Analyst workflow fields (Section 0.4.4)
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    analyst_notes: Optional[str] = None

    metadata: dict = Field(default_factory=dict)
    source_info: SourceInfoRecord
    created_at: datetime
    updated_at: datetime
