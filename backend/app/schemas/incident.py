from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SourceInfoOut(BaseModel):
    name: str
    type: str
    credibility: str
    credibility_score: float = Field(alias="credibilityScore")
    logo_initials: str = Field(alias="logoInitials")
    url: str | None = None
    verified_by: list[str] = Field(default_factory=list, alias="verifiedBy")

    model_config = {"populate_by_name": True}


class IncidentLocationOut(BaseModel):
    lat: float
    lng: float


class IncidentCreate(BaseModel):
    title: str
    description: str
    raw_text: str | None = None
    category: str
    severity: str
    region: str
    location_name: str
    lat: float
    lng: float
    source: str = "manual"
    source_name: str = "Manual Report"
    source_type: str = "government"
    source_url: str | None = None
    language: str = "en"


class IncidentStatusUpdate(BaseModel):
    status: str


class AnalystReviewUpdate(BaseModel):
    """Analyst workflow update — Section 0.4.4."""
    category: Optional[str] = None
    severity: Optional[str] = None
    verification_status: Optional[str] = None
    analyst_notes: Optional[str] = None


class IncidentOut(BaseModel):
    id: str
    source: str
    source_id: str | None = None
    source_url: str | None = None
    title: str
    description: str
    raw_text: str
    processed_text: str | None = None
    category: str
    severity: str
    location: IncidentLocationOut
    location_name: str
    region: str
    country: str
    sentiment_score: float
    risk_score: float
    entities: list[str]
    keywords: list[str]
    language: str
    is_verified: bool
    status: str
    processing_status: str = "pending"
    # Data integrity fields
    verification_status: str = "unverified"
    confidence_score: Optional[float] = None
    # Analyst fields
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    analyst_notes: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    source_info: SourceInfoOut
    created_at: datetime
    updated_at: datetime


class GeoFeatureGeometry(BaseModel):
    type: str = "Point"
    coordinates: list[float]


class GeoFeatureProperties(BaseModel):
    id: str
    title: str
    severity: str
    category: str
    region: str
    risk_score: float
    sentiment_score: float = 0.0
    verification_status: str = "unverified"
    created_at: datetime


class GeoFeature(BaseModel):
    type: str = "Feature"
    geometry: GeoFeatureGeometry
    properties: GeoFeatureProperties


class IncidentGeoFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[GeoFeature]
