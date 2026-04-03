from __future__ import annotations

from dataclasses import asdict, is_dataclass

from fastapi import APIRouter, Depends, Query

from app.api.v1.endpoints.auth import _current_user
from app.models.user import UserRecord
from app.schemas.common import ApiResponse
from app.schemas.official_feed import OfficialFeedPostOut
from app.services.official_feeds import official_feed_service

router = APIRouter()


def _serialize_post(post: object) -> dict[str, object]:
    if is_dataclass(post):
        return asdict(post)
    if hasattr(post, "__dict__"):
        return dict(vars(post))
    raise TypeError("Unsupported official feed post payload")


@router.get("", response_model=ApiResponse[list[OfficialFeedPostOut]])
async def list_official_feed_posts(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[list[OfficialFeedPostOut]]:
    _ = current_user
    posts = await official_feed_service.fetch_posts(limit=limit)
    return ApiResponse(data=[OfficialFeedPostOut.model_validate(_serialize_post(post)) for post in posts])
