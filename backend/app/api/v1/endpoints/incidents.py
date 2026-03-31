from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.endpoints.auth import _current_user
from app.models.user import UserRecord
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.incident import (
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
from app.services.websocket_manager import websocket_manager

router = APIRouter()


@router.get("/geo", response_model=ApiResponse[IncidentGeoFeatureCollection])
async def incidents_geo(
    bbox: str | None = Query(default=None),
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[IncidentGeoFeatureCollection]:
    _ = current_user
    incidents = local_store.list_incidents()
    if bbox:
        west, south, east, north = [float(value) for value in bbox.split(",")]
        incidents = [incident for incident in incidents if west <= incident.location.lng <= east and south <= incident.location.lat <= north]
    features = [
        GeoFeature(
            geometry=GeoFeatureGeometry(coordinates=[incident.location.lng, incident.location.lat]),
            properties=GeoFeatureProperties(
                id=incident.id,
                title=incident.title,
                severity=incident.severity,
                category=incident.category,
                region=incident.region,
                risk_score=incident.risk_score,
                created_at=incident.created_at,
            ),
        )
        for incident in incidents
    ]
    return ApiResponse(data=IncidentGeoFeatureCollection(features=features))


@router.get("/live", response_model=ApiResponse[list[IncidentOut]])
async def live_incidents(
    limit: int = Query(default=25, ge=1, le=50),
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[list[IncidentOut]]:
    _ = current_user
    incidents = await live_news_service.fetch_current_incidents(limit=limit)
    return ApiResponse(data=[IncidentOut.model_validate(item.model_dump()) for item in incidents])


@router.get("", response_model=ApiResponse[PaginatedData[IncidentOut]])
async def list_incidents(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    category: str | None = None,
    severity: str | None = None,
    region: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[PaginatedData[IncidentOut]]:
    _ = current_user
    incidents = local_store.list_incidents()
    if category:
        incidents = [incident for incident in incidents if incident.category == category]
    if severity:
        incidents = [incident for incident in incidents if incident.severity == severity]
    if region:
        incidents = [incident for incident in incidents if incident.region == region]
    if start_date:
        incidents = [incident for incident in incidents if incident.created_at.isoformat() >= start_date]
    if end_date:
        incidents = [incident for incident in incidents if incident.created_at.isoformat() <= end_date]
    if search:
        lowered = search.lower()
        incidents = [
            incident
            for incident in incidents
            if lowered in incident.title.lower() or lowered in incident.description.lower() or lowered in incident.raw_text.lower()
        ]
    incidents.sort(key=lambda item: item.created_at, reverse=True)
    total = len(incidents)
    start = (page - 1) * per_page
    items = [IncidentOut.model_validate(item.model_dump()) for item in incidents[start : start + per_page]]
    return ApiResponse(data=PaginatedData(items=items, page=page, per_page=per_page, total=total))


@router.get("/{incident_id}", response_model=ApiResponse[IncidentOut])
async def get_incident(incident_id: str, current_user: UserRecord = Depends(_current_user)) -> ApiResponse[IncidentOut]:
    _ = current_user
    incident = local_store.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return ApiResponse(data=IncidentOut.model_validate(incident.model_dump()))


@router.post("", response_model=ApiResponse[IncidentOut], status_code=201)
async def create_incident(payload: IncidentCreate, current_user: UserRecord = Depends(_current_user)) -> ApiResponse[IncidentOut]:
    _ = current_user
    incident = data_ingestion_service.create_manual_incident(payload)
    created = local_store.create_incident(incident)
    await websocket_manager.broadcast("incident", {"id": created.id, "title": created.title, "region": created.region, "severity": created.severity})
    return ApiResponse(data=IncidentOut.model_validate(created.model_dump()))


@router.patch("/{incident_id}/status", response_model=ApiResponse[IncidentOut])
async def update_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[IncidentOut]:
    _ = current_user
    try:
        incident = local_store.update_incident_status(incident_id, payload.status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Incident not found") from exc
    await websocket_manager.broadcast("incident", {"id": incident.id, "status": incident.status, "region": incident.region})
    return ApiResponse(data=IncidentOut.model_validate(incident.model_dump()))
