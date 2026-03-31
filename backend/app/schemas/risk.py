from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RiskScoreOut(BaseModel):
    id: str
    region: str
    overall_score: float
    sentiment_component: float
    volume_component: float
    keyword_component: float
    behavior_component: float
    geospatial_component: float
    prediction_horizon: str
    confidence: float
    model_version: str
    calculated_at: datetime


class RiskPredictionOut(BaseModel):
    region: str
    horizon: str
    predicted_score: float
    confidence: float
    predicted_for: datetime


class RiskRecalculateRequest(BaseModel):
    region: str | None = None
