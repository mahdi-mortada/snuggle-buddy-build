from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
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

    app_name: str = "CrisisShield API"
    app_version: str = "1.0.0"
    environment: str = "development"
    storage_mode: str = "local"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/crisisshield"
    mongodb_url: str = "mongodb://localhost:27017/crisisshield"
    elasticsearch_url: str = "http://localhost:9200"
    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap_servers: str = "localhost:9092"
    claude_api_key: str = ""
    jwt_secret_key: str = "crisisshield-dev-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:8080",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ]
    )

    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    local_data_file: Path = BACKEND_DIR / "data" / "local_state.json"
    live_news_enabled: bool = True
    live_news_window_hours: int = 24
    live_news_limit: int = 25
    official_feeds_enabled: bool = True
    official_feed_limit: int = 24
    official_feed_extra_channels_json: str = ""
    official_feed_filter_keywords: str = ""
    admin_email: str = "admin@crisisshield.dev"
    admin_password: str = "admin12345"
    admin_full_name: str = "CrisisShield Admin"
    admin_organization: str = "CrisisShield"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
