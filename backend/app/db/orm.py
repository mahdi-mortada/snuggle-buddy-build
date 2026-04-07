"""SQLAlchemy ORM models for PostgreSQL + PostGIS.

These are separate from the Pydantic models used by the local store.
The Pydantic models handle API serialization; these handle DB persistence.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geography, Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class RegionORM(Base):
    __tablename__ = "regions"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    name_ar = Column(String(100))
    type = Column(String(50), nullable=False)  # "governorate" | "district"
    geometry = Column(Geometry("POLYGON", srid=4326))
    centroid = Column(Geography("POINT", srid=4326))
    centroid_lat = Column(Float)
    centroid_lng = Column(Float)


class UserORM(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(
        String(50),
        default="analyst",
        nullable=False,
    )
    organization = Column(String(255))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin','analyst','viewer','officer')",
            name="users_role_check",
        ),
    )


class IncidentORM(Base):
    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    source = Column(String(50), nullable=False)
    source_id = Column(String(255))
    source_url = Column(Text)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    raw_text = Column(Text, nullable=False)
    processed_text = Column(Text)
    category = Column(String(100))
    severity = Column(String(20))
    # PostGIS point: (longitude, latitude)
    location = Column(Geography("POINT", srid=4326))
    location_name = Column(String(255))
    region = Column(String(100))
    country = Column(String(100), default="Lebanon")
    sentiment_score = Column(Float)
    risk_score = Column(Float)
    entities = Column(JSONB, default=list)
    keywords = Column(JSONB, default=list)
    language = Column(String(10), default="ar")
    is_verified = Column(Boolean, default=False, nullable=False)
    status = Column(String(20), default="new", nullable=False)
    processing_status = Column(String(20), default="pending")
    # Data integrity fields
    verification_status = Column(String(20), default="unverified", nullable=False)
    confidence_score = Column(Float)
    # Analyst workflow fields
    reviewed_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True))
    analyst_notes = Column(Text)
    # Source info (stored as JSONB)
    source_info = Column(JSONB, default=dict)
    extra_metadata = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "source IN ('social_media','news','web_scraping','manual','sensor','crowdsource')",
            name="incidents_source_check",
        ),
        CheckConstraint(
            "category IN ('violence','protest','natural_disaster','infrastructure','health',"
            "'terrorism','cyber','armed_conflict','other')",
            name="incidents_category_check",
        ),
        CheckConstraint(
            "severity IN ('low','medium','high','critical')",
            name="incidents_severity_check",
        ),
        CheckConstraint(
            "status IN ('new','processing','analyzed','escalated','resolved','false_alarm')",
            name="incidents_status_check",
        ),
        CheckConstraint(
            "verification_status IN ('unverified','reviewed','confirmed','rejected')",
            name="incidents_verification_status_check",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="incidents_confidence_score_check",
        ),
        Index("idx_incidents_location", "location", postgresql_using="gist"),
        Index("idx_incidents_created", "created_at"),
        Index("idx_incidents_category", "category"),
        Index("idx_incidents_severity", "severity"),
        Index("idx_incidents_risk", "risk_score"),
        Index("idx_incidents_region", "region"),
    )


class RiskScoreORM(Base):
    __tablename__ = "risk_scores"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    region = Column(String(100), nullable=False)
    overall_score = Column(Float, nullable=False)
    sentiment_component = Column(Float, default=0)
    volume_component = Column(Float, default=0)
    keyword_component = Column(Float, default=0)
    behavior_component = Column(Float, default=0)
    geospatial_component = Column(Float, default=0)
    prediction_horizon = Column(String(20), default="current")
    confidence = Column(Float)
    model_version = Column(String(50))
    # Extra fields for prediction records
    predicted_score = Column(Float)
    predicted_for = Column(DateTime(timezone=True))
    is_prediction = Column(Boolean, default=False)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_risk_region_time", "region", "calculated_at"),
    )


class AlertORM(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    risk_score_id = Column(UUID(as_uuid=False), ForeignKey("risk_scores.id"), nullable=True)
    incident_id = Column(UUID(as_uuid=False), ForeignKey("incidents.id"), nullable=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    recommendation = Column(Text)
    region = Column(String(100))
    is_acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True))
    notification_channels = Column(JSONB, default=["dashboard"])
    linked_incidents = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('threshold_breach','anomaly','escalation','trend','prediction')",
            name="alerts_type_check",
        ),
        CheckConstraint(
            "severity IN ('info','warning','critical','emergency')",
            name="alerts_severity_check",
        ),
    )
