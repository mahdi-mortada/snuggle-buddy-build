from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.endpoints.auth import _current_user
from app.models.user import UserRecord
from app.schemas.alert import AlertOut, AlertStatsOut
from app.schemas.common import ApiResponse
from app.services.local_store import local_store
from app.services.websocket_manager import websocket_manager

router = APIRouter()


@router.get("", response_model=ApiResponse[list[AlertOut]])
async def list_alerts(severity: str | None = Query(default=None), current_user: UserRecord = Depends(_current_user)) -> ApiResponse[list[AlertOut]]:
    _ = current_user
    alerts = local_store.list_alerts()
    if severity:
        alerts = [alert for alert in alerts if alert.severity == severity]
    alerts.sort(key=lambda item: item.created_at, reverse=True)
    return ApiResponse(data=[AlertOut.model_validate(alert.model_dump()) for alert in alerts])


@router.get("/stats", response_model=ApiResponse[AlertStatsOut])
async def alert_stats(current_user: UserRecord = Depends(_current_user)) -> ApiResponse[AlertStatsOut]:
    _ = current_user
    alerts = local_store.list_alerts()
    acknowledged = [alert for alert in alerts if alert.is_acknowledged]
    by_severity: dict[str, int] = {}
    response_times: list[float] = []
    for alert in alerts:
        by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1
        if alert.acknowledged_at:
            response_times.append((alert.acknowledged_at - alert.created_at).total_seconds() / 60)
    stats = AlertStatsOut(
        total=len(alerts),
        acknowledged=len(acknowledged),
        by_severity=by_severity,
        average_response_minutes=round(sum(response_times) / len(response_times), 2) if response_times else 0.0,
    )
    return ApiResponse(data=stats)


@router.get("/{alert_id}", response_model=ApiResponse[AlertOut])
async def get_alert(alert_id: str, current_user: UserRecord = Depends(_current_user)) -> ApiResponse[AlertOut]:
    _ = current_user
    alert = local_store.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return ApiResponse(data=AlertOut.model_validate(alert.model_dump()))


@router.patch("/{alert_id}/acknowledge", response_model=ApiResponse[AlertOut])
async def acknowledge_alert(alert_id: str, current_user: UserRecord = Depends(_current_user)) -> ApiResponse[AlertOut]:
    try:
        alert = local_store.acknowledge_alert(alert_id, current_user.id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Alert not found") from exc
    await websocket_manager.broadcast("alert", {"id": alert.id, "region": alert.region, "is_acknowledged": alert.is_acknowledged})
    return ApiResponse(data=AlertOut.model_validate(alert.model_dump()))
