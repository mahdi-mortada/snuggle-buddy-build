from __future__ import annotations

from dataclasses import asdict, is_dataclass

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.endpoints.auth import _current_user
from app.models.user import UserRecord
from app.schemas.common import ApiResponse
from app.schemas.official_feed import OfficialFeedPostOut
from app.schemas.source import SourceCreate, SourceOut, SourceUpdate
from app.services.official_feeds import official_feed_service
from app.services.source_registry import SourceRegistryError, source_registry_service

router = APIRouter()


def _serialize_post(post: object) -> dict[str, object]:
    if is_dataclass(post):
        return asdict(post)
    if hasattr(post, "__dict__"):
        return dict(vars(post))
    raise TypeError("Unsupported official feed post payload")


@router.get("", response_model=ApiResponse[list[OfficialFeedPostOut]])
async def list_official_feed_posts(
    limit: int = Query(default=24, ge=1, le=60),
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[list[OfficialFeedPostOut]]:
    _ = current_user
    posts = await official_feed_service.fetch_posts(limit=limit)
    return ApiResponse(data=[OfficialFeedPostOut.model_validate(_serialize_post(post)) for post in posts])


@router.get("/sources", response_model=ApiResponse[list[SourceOut]])
async def list_official_feed_sources(
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[list[SourceOut]]:
    _ = current_user
    sources = source_registry_service.list_sources()
    return ApiResponse(data=[SourceOut.model_validate(source.model_dump(mode="json")) for source in sources])


@router.post("/sources", response_model=ApiResponse[SourceOut], status_code=201)
async def create_official_feed_source(
    payload: SourceCreate,
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[SourceOut]:
    _ = current_user
    try:
        source = await source_registry_service.create_source(
            source_type=payload.source_type,
            raw_input=payload.input,
            name=payload.name,
        )
    except SourceRegistryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    official_feed_service.invalidate_cache()
    return ApiResponse(data=SourceOut.model_validate(source.model_dump(mode="json")))


@router.patch("/sources/{source_id}", response_model=ApiResponse[SourceOut])
async def update_official_feed_source(
    source_id: str,
    payload: SourceUpdate,
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[SourceOut]:
    _ = current_user
    try:
        source = source_registry_service.update_source(source_id, is_active=payload.is_active)
    except SourceRegistryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    official_feed_service.invalidate_cache()
    return ApiResponse(data=SourceOut.model_validate(source.model_dump(mode="json")))


@router.delete("/sources/{source_id}", response_model=ApiResponse[SourceOut])
async def delete_official_feed_source(
    source_id: str,
    current_user: UserRecord = Depends(_current_user),
) -> ApiResponse[SourceOut]:
    _ = current_user
    try:
        source = source_registry_service.delete_source(source_id)
    except SourceRegistryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    official_feed_service.invalidate_cache()
    return ApiResponse(data=SourceOut.model_validate(source.model_dump(mode="json")))
