from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", PROJECT_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────────────────
    app_name: str = "CrisisShield API"
    app_version: str = "1.0.0"
    environment: str = "development"
    storage_mode: str = "local"  # "local" | "postgres"

    # ── Databases ────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/crisisshield"
    mongodb_url: str = "mongodb://localhost:27017/crisisshield"
    elasticsearch_url: str = "http://localhost:9200"
    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap_servers: str = "localhost:29092"

    # ── Authentication ───────────────────────────────────────────────────────
    jwt_secret_key: str = "crisisshield-dev-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:8080",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://localhost:3000",
            "http://localhost:3002",      # Docker frontend (nginx prod build)
            "http://127.0.0.1:3002",
        ]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    # ── Admin Seed Account ───────────────────────────────────────────────────
    admin_email: str = "admin@crisisshield.dev"
    admin_password: str = "admin12345"
    admin_full_name: str = "CrisisShield Admin"
    admin_organization: str = "CrisisShield"

    # ── AI / LLM ─────────────────────────────────────────────────────────────
    claude_api_key: str = ""

    # ── Notifications ────────────────────────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "alerts@crisisshield.dev"
    smtp_from_name: str = "CrisisShield Alerts"
    alert_email_recipients: str = ""  # comma-separated

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_phone: str = ""
    alert_sms_recipients: str = ""  # comma-separated

    alert_webhook_urls: str = ""  # comma-separated

    # ── ML / MLflow ──────────────────────────────────────────────────────────
    mlflow_tracking_uri: str = "http://localhost:5001"
    mlflow_risk_experiment: str = "crisisshield_risk_scoring"
    mlflow_escalation_experiment: str = "crisisshield_escalation"

    # ── Alert Thresholds ─────────────────────────────────────────────────────
    alert_threshold_info: float = 40.0
    alert_threshold_warning: float = 60.0
    alert_threshold_critical: float = 80.0
    alert_threshold_emergency: float = 90.0
    alert_velocity_threshold: float = 20.0
    alert_escalation_probability_threshold: float = 0.8
    alert_rate_limit_seconds: int = 3600

    # ── Risk Scoring Weights ─────────────────────────────────────────────────
    risk_weight_sentiment: float = 0.25
    risk_weight_volume: float = 0.25
    risk_weight_keyword: float = 0.20
    risk_weight_behavior: float = 0.15
    risk_weight_geospatial: float = 0.15
    risk_recalc_interval_minutes: int = 15

    # ── NLP ──────────────────────────────────────────────────────────────────
    hf_home: str = "/tmp/huggingface_cache"
    tokenizers_parallelism: str = "false"

    # ── Data Ingestion ────────────────────────────────────────────────────────
    live_news_enabled: bool = True
    live_news_window_hours: int = 24
    live_news_limit: int = 25
    official_feeds_enabled: bool = True
    official_feed_limit: int = 24
    official_feed_extra_channels_json: str = ""

    # ── Server ───────────────────────────────────────────────────────────────
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    local_data_file: Path = BACKEND_DIR / "data" / "local_state.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
