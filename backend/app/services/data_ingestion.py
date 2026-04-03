from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.models.incident import IncidentLocation, IncidentRecord, SourceInfoRecord
from app.schemas.incident import IncidentCreate
from app.services.nlp_pipeline import nlp_pipeline


class DataIngestionService:
    def create_manual_incident(self, payload: IncidentCreate) -> IncidentRecord:
        analyzed = nlp_pipeline.analyze(payload.raw_text or payload.description)
        now = datetime.now(UTC)
        return IncidentRecord(
            id=str(uuid4()),
            source=payload.source,  # type: ignore[arg-type]
            source_id=None,
            title=payload.title,
            description=payload.description,
            raw_text=payload.raw_text or payload.description,
            category=payload.category,  # type: ignore[arg-type]
            severity=payload.severity,  # type: ignore[arg-type]
            location=IncidentLocation(lat=payload.lat, lng=payload.lng),
            location_name=payload.location_name,
            region=payload.region,
            sentiment_score=float(analyzed["sentiment_score"]),
            risk_score=min(100.0, max(0.0, 45.0 + len(str(analyzed["keywords"])) * 3)),
            entities=list(analyzed["entities"]),  # type: ignore[arg-type]
            keywords=list(analyzed["keywords"]),  # type: ignore[arg-type]
            language=payload.language,
            status="new",
            source_info=SourceInfoRecord(
                name=payload.source_name,
                type=payload.source_type,  # type: ignore[arg-type]
                credibility="moderate",
                credibilityScore=65,
                logoInitials="MR",
                url=payload.source_url,
            ),
            source_url=payload.source_url,
            created_at=now,
            updated_at=now,
        )


data_ingestion_service = DataIngestionService()
