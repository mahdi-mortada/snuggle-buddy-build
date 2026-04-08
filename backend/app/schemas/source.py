from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SourceCreate(BaseModel):
    source_type: str = "telegram"
    name: str | None = None
    input: str


class SourceUpdate(BaseModel):
    is_active: bool


class SourceOut(BaseModel):
    id: str
    source_type: str
    name: str
    username: str
    telegram_id: int | None = None
    is_active: bool
    is_custom: bool
    created_at: datetime
