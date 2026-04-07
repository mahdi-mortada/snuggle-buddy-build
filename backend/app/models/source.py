from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, model_validator


SourceKind = Literal["telegram", "rss"]


class SourceRecord(BaseModel):
    id: str
    source_type: SourceKind
    name: str
    username: str
    telegram_id: int | None = None
    is_active: bool = True
    is_custom: bool = False
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        data = dict(value)
        legacy_identifier = data.pop("identifier", None)
        if "username" not in data and isinstance(legacy_identifier, str):
            data["username"] = legacy_identifier

        data["username"] = str(data.get("username", "")).strip().lstrip("@").lower()

        if data.get("telegram_id") in {"", None}:
            data["telegram_id"] = None

        return data


DEFAULT_SOURCE_SEEDS: tuple[tuple[str, str], ...] = (
    ("LBCI", "LBCI_NEWS"),
    ("MTV Lebanon", "MTVLebanoNews"),
    ("Al Jadeed", "Aljadeedtelegram"),
    ("Al Manar", "almanarnews"),
)


def build_source_id(source_type: str, unique_value: str | int) -> str:
    normalized_unique_value = str(unique_value).strip().lstrip("@").lower()
    return f"source-{uuid5(NAMESPACE_URL, f'{source_type}:{normalized_unique_value}')}"


def build_default_sources() -> list[SourceRecord]:
    created_at = datetime.now(UTC)
    return [
        SourceRecord(
            id=build_source_id("telegram", username),
            source_type="telegram",
            name=name,
            username=username,
            telegram_id=None,
            is_active=True,
            is_custom=False,
            created_at=created_at,
        )
        for name, username in DEFAULT_SOURCE_SEEDS
    ]
