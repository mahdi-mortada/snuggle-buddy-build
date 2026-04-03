"""Initial CrisisShield schema with PostGIS and all tables.

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── PostGIS extension ───────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # fuzzy matching

    # ── regions ─────────────────────────────────────────────────────────────
    op.create_table(
        "regions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_ar", sa.String(100), nullable=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column(
            "geometry",
            sa.Text(),  # stored as WKT; PostGIS handles actual type
            nullable=True,
        ),
        sa.Column("centroid_lat", sa.Float(), nullable=True),
        sa.Column("centroid_lng", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # Add PostGIS geometry columns properly
    op.execute(
        "ALTER TABLE regions ADD COLUMN IF NOT EXISTS geom geometry(POLYGON, 4326)"
    )
    op.execute(
        "ALTER TABLE regions ADD COLUMN IF NOT EXISTS centroid geography(POINT, 4326)"
    )
    op.execute("DROP COLUMN IF EXISTS regions.geometry")
    op.execute("CREATE INDEX idx_regions_geom ON regions USING GIST(geom)")

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=False), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="analyst"),
        sa.Column("organization", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "role IN ('admin','analyst','viewer','officer')",
            name="users_role_check",
        ),
        sa.UniqueConstraint("email"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── incidents ────────────────────────────────────────────────────────────
    op.create_table(
        "incidents",
        sa.Column("id", UUID(as_uuid=False), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("processed_text", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("location_name", sa.String(255), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=True, server_default="Lebanon"),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("entities", JSONB(), nullable=True),
        sa.Column("keywords", JSONB(), nullable=True),
        sa.Column("language", sa.String(10), nullable=True, server_default="ar"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("processing_status", sa.String(20), nullable=True, server_default="pending"),
        sa.Column(
            "verification_status",
            sa.String(20),
            nullable=False,
            server_default="unverified",
        ),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column(
            "reviewed_by",
            UUID(as_uuid=False),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analyst_notes", sa.Text(), nullable=True),
        sa.Column("source_info", JSONB(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "source IN ('social_media','news','web_scraping','manual','sensor','crowdsource')",
            name="incidents_source_check",
        ),
        sa.CheckConstraint(
            "category IN ('violence','protest','natural_disaster','infrastructure','health',"
            "'terrorism','cyber','armed_conflict','other')",
            name="incidents_category_check",
        ),
        sa.CheckConstraint(
            "severity IN ('low','medium','high','critical')",
            name="incidents_severity_check",
        ),
        sa.CheckConstraint(
            "status IN ('new','processing','analyzed','escalated','resolved','false_alarm')",
            name="incidents_status_check",
        ),
        sa.CheckConstraint(
            "verification_status IN ('unverified','reviewed','confirmed','rejected')",
            name="incidents_verification_status_check",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Add PostGIS geography column for GPS location
    op.execute(
        "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS location geography(POINT, 4326)"
    )
    op.execute("CREATE INDEX idx_incidents_location ON incidents USING GIST(location)")
    op.execute("CREATE INDEX idx_incidents_created ON incidents(created_at DESC)")
    op.execute("CREATE INDEX idx_incidents_category ON incidents(category)")
    op.execute("CREATE INDEX idx_incidents_severity ON incidents(severity)")
    op.execute("CREATE INDEX idx_incidents_risk ON incidents(risk_score DESC)")
    op.execute("CREATE INDEX idx_incidents_region ON incidents(region)")
    # Trigram index for fuzzy region search
    op.execute(
        "CREATE INDEX idx_incidents_region_trgm ON incidents USING GIN(region gin_trgm_ops)"
    )

    # ── risk_scores ──────────────────────────────────────────────────────────
    op.create_table(
        "risk_scores",
        sa.Column("id", UUID(as_uuid=False), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("sentiment_component", sa.Float(), nullable=True, server_default="0"),
        sa.Column("volume_component", sa.Float(), nullable=True, server_default="0"),
        sa.Column("keyword_component", sa.Float(), nullable=True, server_default="0"),
        sa.Column("behavior_component", sa.Float(), nullable=True, server_default="0"),
        sa.Column("geospatial_component", sa.Float(), nullable=True, server_default="0"),
        sa.Column("prediction_horizon", sa.String(20), nullable=True, server_default="current"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("predicted_score", sa.Float(), nullable=True),
        sa.Column("predicted_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_prediction", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE INDEX idx_risk_region_time ON risk_scores(region, calculated_at DESC)"
    )

    # ── alerts ───────────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", UUID(as_uuid=False), nullable=False),
        sa.Column(
            "risk_score_id",
            UUID(as_uuid=False),
            sa.ForeignKey("risk_scores.id"),
            nullable=True,
        ),
        sa.Column(
            "incident_id",
            UUID(as_uuid=False),
            sa.ForeignKey("incidents.id"),
            nullable=True,
        ),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("is_acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "acknowledged_by",
            UUID(as_uuid=False),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notification_channels", JSONB(), nullable=True),
        sa.Column("linked_incidents", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "alert_type IN ('threshold_breach','anomaly','escalation','trend','prediction')",
            name="alerts_type_check",
        ),
        sa.CheckConstraint(
            "severity IN ('info','warning','critical','emergency')",
            name="alerts_severity_check",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("risk_scores")
    op.drop_table("incidents")
    op.drop_table("users")
    op.drop_table("regions")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
