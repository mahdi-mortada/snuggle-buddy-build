from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.incident import SourceInfoOut


class OfficialFeedPostOut(BaseModel):
    id: str
    platform: str
    publisher_name: str
    account_label: str
    account_handle: str
    account_url: str
    post_url: str
    content: str
    signal_tags: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    primary_keyword: str | None = None
    source_info: SourceInfoOut
    published_at: datetime

