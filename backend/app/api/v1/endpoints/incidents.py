from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.endpoints.auth import _current_user
from app.config import get_settings
from app.db.elasticsearch import elasticsearch_client
from app.models.user import UserRecord
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.incident import (
    AnalystReviewUpdate,
    GeoFeature,
    GeoFeatureGeometry,
    GeoFeatureProperties,
    IncidentCreate,
    IncidentGeoFeatureCollection,
    IncidentOut,
    IncidentStatusUpdate,
)
from app.services.data_ingestion import data_ingestion_service
from app.services.live_news import live_news_service
from app.services.local_store import local_store
from app.services.location_resolver import resolve_location
from app.services.websocket_manager import websocket_manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/geo", response_model=ApiResponse[IncidentGeoFeatureCollection])
async def incidents_geo(
    bbox: Optional[str] = Query(default=None, description="west,south,east,north"),
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[IncidentGeoFeatureCollection]:
    """GeoJSON of all incidents for map rendering. Supports bbox spatial filter."""
    _ = current_user
    settings = get_settings()

    incidents = local_store.list_incidents()

    if bbox:
        try:
            west, south, east, north = [float(v) for v in bbox.split(",")]
        except ValueError:
            raise HTTPException(status_code=400, detail="bbox must be 'west,south,east,north'")
        incidents = [
            i for i in incidents
            if west <= i.location.lng <= east and south <= i.location.lat <= north
        ]

    features = [
        GeoFeature(
            geometry=GeoFeatureGeometry(coordinates=[i.location.lng, i.location.lat]),
            properties=GeoFeatureProperties(
                id=i.id,
                title=i.title,
                severity=i.severity,
                category=i.category,
                region=i.region,
                risk_score=i.risk_score,
                sentiment_score=i.sentiment_score,
                verification_status=getattr(i, "verification_status", "unverified"),
                created_at=i.created_at,
            ),
        )
        for i in incidents
    ]
    return ApiResponse(data=IncidentGeoFeatureCollection(features=features))


@router.get("/live", response_model=ApiResponse[list[IncidentOut]])
async def live_incidents(
    limit: int = Query(default=100, ge=1, le=100),
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[list[IncidentOut]]:
    """Live incidents from the ingestion pipeline (last 48h)."""
    _ = current_user
    incidents = await live_news_service.fetch_current_incidents(limit=limit)
    return ApiResponse(
        data=[IncidentOut.model_validate(item.model_dump(mode="json")) for item in incidents]
    )


@router.get("", response_model=ApiResponse[PaginatedData[IncidentOut]])
async def list_incidents(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    category: Optional[str] = None,
    severity: Optional[str] = None,
    region: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[PaginatedData[IncidentOut]]:
    """
    List incidents with pagination and filtering.
    Uses Elasticsearch for full-text search when connected; falls back to in-memory filter.
    """
    _ = current_user

    # ── Elasticsearch path ────────────────────────────────────────────────────
    if search and elasticsearch_client.is_connected:
        filters: dict = {}
        if category:
            filters["category"] = category
        if severity:
            filters["severity"] = severity
        if region:
            filters["region"] = region

        es_result = await elasticsearch_client.search_incidents(
            query=search,
            filters=filters if filters else None,
            page=page,
            per_page=per_page,
        )
        hits = es_result.get("hits", {})
        total = hits.get("total", {}).get("value", 0)
        raw_items = hits.get("hits", [])

        # Hydrate from local store by id (ES stores index, local store has full record)
        items: list[IncidentOut] = []
        for hit in raw_items:
            doc_id = hit.get("_id") or hit.get("_source", {}).get("id")
            incident = local_store.get_incident(doc_id) if doc_id else None
            if incident:
                items.append(IncidentOut.model_validate(incident.model_dump(mode="json")))

        return ApiResponse(
            data=PaginatedData(items=items, page=page, per_page=per_page, total=total)
        )

    # ── Local store path ──────────────────────────────────────────────────────
    incidents = local_store.list_incidents()

    if category:
        incidents = [i for i in incidents if i.category == category]
    if severity:
        incidents = [i for i in incidents if i.severity == severity]
    if region:
        incidents = [i for i in incidents if i.region == region]
    if start_date:
        incidents = [i for i in incidents if i.created_at.isoformat() >= start_date]
    if end_date:
        incidents = [i for i in incidents if i.created_at.isoformat() <= end_date]
    if search:
        lowered = search.lower()
        incidents = [
            i for i in incidents
            if lowered in i.title.lower()
            or lowered in i.description.lower()
            or lowered in i.raw_text.lower()
        ]

    incidents.sort(key=lambda i: i.created_at, reverse=True)
    total = len(incidents)
    start = (page - 1) * per_page
    items = [
        IncidentOut.model_validate(i.model_dump(mode="json"))
        for i in incidents[start : start + per_page]
    ]
    return ApiResponse(data=PaginatedData(items=items, page=page, per_page=per_page, total=total))


@router.get("/{incident_id}", response_model=ApiResponse[IncidentOut])
async def get_incident(
    incident_id: str,
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[IncidentOut]:
    """Get single incident with full details."""
    _ = current_user
    incident = local_store.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return ApiResponse(data=IncidentOut.model_validate(incident.model_dump(mode="json")))


@router.post("", response_model=ApiResponse[IncidentOut], status_code=201)
async def create_incident(
    payload: IncidentCreate,
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[IncidentOut]:
    """Manually create an incident (analyst/admin only)."""
    _ = current_user

    # Auto-resolve region if not provided or validate existing
    if not payload.region or payload.region == "unknown":
        resolution = await resolve_location(
            gps_lat=payload.lat,
            gps_lng=payload.lng,
            text_location=payload.location_name,
        )
        if resolution["region"] != "unknown":
            payload.region = resolution["region"]

    incident = data_ingestion_service.create_manual_incident(payload)
    created = local_store.create_incident(incident)

    # Index in Elasticsearch
    if elasticsearch_client.is_connected:
        await elasticsearch_client.index_incident({
            "id": created.id,
            "title": created.title,
            "description": created.description,
            "raw_text": created.raw_text,
            "category": created.category,
            "severity": created.severity,
            "region": created.region,
            "risk_score": created.risk_score,
            "sentiment_score": created.sentiment_score,
            "is_verified": created.is_verified,
            "location": {"lat": created.location.lat, "lon": created.location.lng},
            "created_at": created.created_at.isoformat(),
        })

    await websocket_manager.broadcast("incident", {
        "id": created.id,
        "title": created.title,
        "region": created.region,
        "severity": created.severity,
    })
    return ApiResponse(data=IncidentOut.model_validate(created.model_dump(mode="json")))


@router.patch("/{incident_id}/status", response_model=ApiResponse[IncidentOut])
async def update_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[IncidentOut]:
    """Update incident processing status."""
    _ = current_user
    try:
        incident = local_store.update_incident_status(incident_id, payload.status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Incident not found") from exc
    await websocket_manager.broadcast("incident", {
        "id": incident.id,
        "status": incident.status,
        "region": incident.region,
    })
    return ApiResponse(data=IncidentOut.model_validate(incident.model_dump(mode="json")))


@router.patch("/{incident_id}/review", response_model=ApiResponse[IncidentOut])
async def analyst_review(
    incident_id: str,
    payload: AnalystReviewUpdate,
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[IncidentOut]:
    """Analyst review: update category, severity, verification status, add notes."""
    from datetime import datetime, timezone

    incident = local_store.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    update_data: dict = {"reviewed_by": current_user.id, "reviewed_at": datetime.now(timezone.utc)}
    if payload.category is not None:
        update_data["category"] = payload.category
    if payload.severity is not None:
        update_data["severity"] = payload.severity
    if payload.verification_status is not None:
        update_data["verification_status"] = payload.verification_status
        update_data["is_verified"] = payload.verification_status in ("confirmed",)
    if payload.analyst_notes is not None:
        update_data["analyst_notes"] = payload.analyst_notes

    updated = local_store.update_incident(incident_id, update_data)
    return ApiResponse(data=IncidentOut.model_validate(updated.model_dump(mode="json")))
