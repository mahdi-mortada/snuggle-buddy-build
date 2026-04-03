from __future__ import annotations

from datetime import datetime
from typing import Optional

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


class RiskRegionDetailOut(BaseModel):
    """Full breakdown for /risk/region/{region}."""
    region: str
    overall_score: float
    sentiment_component: float
    volume_component: float
    keyword_component: float
    behavior_component: float
    geospatial_component: float
    confidence: float
    is_anomalous: bool = False
    anomaly_score: Optional[float] = None
    escalation_probability: Optional[float] = None
    incident_count_24h: int = 0
    calculated_at: datetime


class RiskPredictionOut(BaseModel):
    region: str
    horizon: str  # "24h" | "48h" | "7d"
    predicted_score: float
    lower_bound: float = 0.0
    upper_bound: float = 100.0
    confidence: float
    escalation_probability: float = 0.0
    predicted_for: datetime
    model_version: str = "prophet-v1"


class RiskRecalculateRequest(BaseModel):
    region: str | None = None


