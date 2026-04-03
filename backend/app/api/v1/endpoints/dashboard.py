from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.endpoints.auth import _current_user
from app.models.user import UserRecord
from app.schemas.common import ApiResponse
from app.services.local_store import local_store

router = APIRouter()


@router.get("/overview", response_model=ApiResponse[dict[str, object]])
async def overview(current_user: UserRecord = Depends(_current_user)) -> ApiResponse[dict[str, object]]:
    _ = current_user
    incidents = local_store.list_incidents()
    alerts = local_store.list_alerts()
    risk_scores = local_store.list_risk_scores()
    avg_risk = round(sum(score.overall_score for score in risk_scores) / max(len(risk_scores), 1), 2)
    highest_region = max(risk_scores, key=lambda score: score.overall_score).region if risk_scores else "Unknown"
    return ApiResponse(
        data={
            "total_incidents_24h": len(incidents),
            "active_alerts": len([alert for alert in alerts if not alert.is_acknowledged]),
            "avg_risk_score": avg_risk,
            "top_risk_region": highest_region,
        }
    )


@router.get("/trends", response_model=ApiResponse[list[dict[str, object]]])
async def trends(current_user: UserRecord = Depends(_current_user)) -> ApiResponse[list[dict[str, object]]]:
    _ = current_user
    return ApiResponse(data=local_store.dashboard_trends())


@router.get("/hotspots", response_model=ApiResponse[list[dict[str, object]]])
async def hotspots(current_user: UserRecord = Depends(_current_user)) -> ApiResponse[list[dict[str, object]]]:
    _ = current_user
    return ApiResponse(data=local_store.dashboard_hotspots())
