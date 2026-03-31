from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.endpoints.auth import _current_user
from app.models.user import UserRecord
from app.schemas.common import ApiResponse
from app.schemas.risk import RiskPredictionOut, RiskRecalculateRequest, RiskScoreOut
from app.services.local_store import local_store
from app.services.websocket_manager import websocket_manager

router = APIRouter()


@router.get("/current", response_model=ApiResponse[list[RiskScoreOut]])
async def current_scores(current_user: UserRecord = Depends(_current_user)) -> ApiResponse[list[RiskScoreOut]]:
    _ = current_user
    return ApiResponse(data=[RiskScoreOut.model_validate(score.model_dump()) for score in local_store.list_risk_scores()])


@router.get("/region/{region}", response_model=ApiResponse[RiskScoreOut])
async def region_score(region: str, current_user: UserRecord = Depends(_current_user)) -> ApiResponse[RiskScoreOut]:
    _ = current_user
    for score in local_store.list_risk_scores():
        if score.region.lower() == region.lower():
            return ApiResponse(data=RiskScoreOut.model_validate(score.model_dump()))
    raise HTTPException(status_code=404, detail="Region not found")


@router.get("/history", response_model=ApiResponse[list[RiskScoreOut]])
async def risk_history(
    region: str | None = Query(default=None),
    points: int = Query(default=7, ge=1, le=30),
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[list[RiskScoreOut]]:
    _ = current_user
    history = [RiskScoreOut.model_validate(score.model_dump()) for score in local_store.risk_history(region=region, points=points)]
    return ApiResponse(data=history)


@router.get("/predictions", response_model=ApiResponse[list[RiskPredictionOut]])
async def risk_predictions(
    region: str | None = Query(default=None),
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[list[RiskPredictionOut]]:
    _ = current_user
    return ApiResponse(data=[RiskPredictionOut.model_validate(prediction.model_dump()) for prediction in local_store.predictions(region=region)])


@router.post("/recalculate", response_model=ApiResponse[list[RiskScoreOut]])
async def recalculate_risk(
    payload: RiskRecalculateRequest,
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[list[RiskScoreOut]]:
    _ = current_user
    scores, _alerts = local_store.recalculate()
    if payload.region:
        scores = [score for score in scores if score.region.lower() == payload.region.lower()]
    for score in scores:
        await websocket_manager.broadcast("risk_update", {"region": score.region, "overall_score": score.overall_score})
    return ApiResponse(data=[RiskScoreOut.model_validate(score.model_dump()) for score in scores])
