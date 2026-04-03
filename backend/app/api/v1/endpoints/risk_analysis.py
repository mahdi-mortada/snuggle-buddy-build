from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.endpoints.auth import _current_user
from app.models.user import UserRecord
from app.schemas.common import ApiResponse
from app.schemas.risk import (
    RiskPredictionOut,
    RiskRecalculateRequest,
    RiskRegionDetailOut,
    RiskScoreOut,
)
from app.services.local_store import local_store
from app.services.websocket_manager import websocket_manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/current", response_model=ApiResponse[list[RiskScoreOut]])
async def current_scores(
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[list[RiskScoreOut]]:
    """Current risk scores for all regions."""
    _ = current_user
    return ApiResponse(
        data=[RiskScoreOut.model_validate(s.model_dump(mode="json")) for s in local_store.list_risk_scores()]
    )


@router.get("/region/{region}", response_model=ApiResponse[RiskRegionDetailOut])
async def region_detail(
    region: str,
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[RiskRegionDetailOut]:
    """Detailed 5-component risk breakdown for a region, with anomaly and escalation data."""
    _ = current_user

    score = None
    for s in local_store.list_risk_scores():
        if s.region.lower() == region.lower():
            score = s
            break

    if not score:
        raise HTTPException(status_code=404, detail="Region not found")

    # Try to get anomaly + escalation data from prediction engine
    is_anomalous = False
    anomaly_score = None
    escalation_probability = None

    try:
        from app.services.anomaly_detection import anomaly_detector
        if anomaly_detector.is_trained:
            features = [
                score.sentiment_component / 100,
                score.volume_component / 100,
                score.keyword_component / 100,
                score.behavior_component / 100,
                score.geospatial_component / 100,
            ]
            result = anomaly_detector.predict([features])
            is_anomalous = result["is_anomalous"]
            anomaly_score = result["score"]
    except Exception as exc:
        logger.debug("Anomaly detection not available: %s", exc)

    try:
        from app.services.escalation_model import escalation_model
        if escalation_model.is_trained:
            escalation_probability = escalation_model.predict_probability(score)
    except Exception as exc:
        logger.debug("Escalation model not available: %s", exc)

    # Count incidents in last 24h for this region
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    incident_count = sum(
        1 for i in local_store.list_incidents()
        if i.region.lower() == region.lower() and i.created_at >= cutoff
    )

    detail = RiskRegionDetailOut(
        region=score.region,
        overall_score=score.overall_score,
        sentiment_component=score.sentiment_component,
        volume_component=score.volume_component,
        keyword_component=score.keyword_component,
        behavior_component=score.behavior_component,
        geospatial_component=score.geospatial_component,
        confidence=score.confidence,
        is_anomalous=is_anomalous,
        anomaly_score=anomaly_score,
        escalation_probability=escalation_probability,
        incident_count_24h=incident_count,
        calculated_at=score.calculated_at,
    )
    return ApiResponse(data=detail)


@router.get("/history", response_model=ApiResponse[list[RiskScoreOut]])
async def risk_history(
    region: Optional[str] = Query(default=None),
    points: int = Query(default=7, ge=1, le=30),
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[list[RiskScoreOut]]:
    """Historical risk scores for trend analysis."""
    _ = current_user
    history = [
        RiskScoreOut.model_validate(s.model_dump(mode="json"))
        for s in local_store.risk_history(region=region, points=points)
    ]
    return ApiResponse(data=history)


@router.get("/predictions", response_model=ApiResponse[list[RiskPredictionOut]])
async def risk_predictions(
    region: Optional[str] = Query(default=None),
    horizon: Optional[str] = Query(default=None, description="24h | 48h | 7d"),
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[list[RiskPredictionOut]]:
    """Forecast risk scores for 24h / 48h / 7d using Prophet."""
    _ = current_user

    # Try real prediction engine first
    try:
        from app.services.prediction_engine import prediction_engine
        predictions = await prediction_engine.get_predictions(region=region, horizon=horizon)
        if predictions:
            return ApiResponse(
                data=[RiskPredictionOut.model_validate(p) for p in predictions]
            )
    except Exception as exc:
        logger.debug("Prediction engine not available, using local store: %s", exc)

    # Fallback to local store predictions
    raw = local_store.predictions(region=region)
    if horizon:
        raw = [p for p in raw if p.horizon == horizon]
    return ApiResponse(
        data=[RiskPredictionOut.model_validate(p.model_dump(mode="json")) for p in raw]
    )


@router.post("/recalculate", response_model=ApiResponse[list[RiskScoreOut]])
async def recalculate_risk(
    payload: RiskRecalculateRequest,
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[list[RiskScoreOut]]:
    """Manually trigger risk recalculation for one or all regions."""
    _ = current_user

    # Try real risk scoring service
    try:
        from app.services.risk_scoring import risk_scoring_service
        scores = await risk_scoring_service.recalculate(region=payload.region)
        if scores:
            for score in scores:
                await websocket_manager.broadcast("risk_update", {
                    "region": score["region"],
                    "overall_score": score["overall_score"],
                })
            return ApiResponse(data=[RiskScoreOut.model_validate(s) for s in scores])
    except Exception as exc:
        logger.debug("Risk scoring service not available, using local store: %s", exc)

    # Fallback
    scores, _alerts = local_store.recalculate()
    if payload.region:
        scores = [s for s in scores if s.region.lower() == payload.region.lower()]
    for score in scores:
        await websocket_manager.broadcast("risk_update", {
            "region": score.region,
            "overall_score": score.overall_score,
        })
    return ApiResponse(
        data=[RiskScoreOut.model_validate(s.model_dump(mode="json")) for s in scores]
    )
