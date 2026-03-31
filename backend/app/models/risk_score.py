from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RiskScoreRecord(BaseModel):
    id: str
    region: str
    overall_score: float
    sentiment_component: float
    volume_component: float
    keyword_component: float
    behavior_component: float
    geospatial_component: float
    prediction_horizon: str = "current"
    confidence: float
    model_version: str = "local-dev-v1"
    calculated_at: datetime


class RiskPredictionRecord(BaseModel):
    region: str
    horizon: str
    predicted_score: float
    confidence: float
    predicted_for: datetime
