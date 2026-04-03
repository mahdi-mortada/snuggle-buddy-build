from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RiskScoreRecord(BaseModel):
    id: str
    region: str
    overall_score: float
    sentiment_component: float = 0.0
    volume_component: float = 0.0
    keyword_component: float = 0.0
    behavior_component: float = 0.0
    geospatial_component: float = 0.0
    prediction_horizon: str = "current"
    confidence: float = 0.0
    model_version: str = "v1.0"
    calculated_at: datetime


class RiskPredictionRecord(BaseModel):
    region: str
    horizon: str  # "24h" | "48h" | "7d"
    predicted_score: float
    lower_bound: float = 0.0
    upper_bound: float = 100.0
    confidence: float = 0.0
    escalation_probability: float = 0.0
    predicted_for: datetime
    model_version: str = "prophet-v1"


class RegionRiskDetail(BaseModel):
    """Full risk breakdown for a single region — returned by /risk/region/{region}."""
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
