"""Hate Speech Monitor API Endpoints.

GET  /api/v1/hate-speech/stats          → aggregated statistics
GET  /api/v1/hate-speech/posts          → flagged post feed (paginated)
GET  /api/v1/hate-speech/all            → all posts (flagged + clean)
POST /api/v1/hate-speech/scan           → trigger manual scan
POST /api/v1/hate-speech/posts/{id}/review → mark post reviewed
POST /api/v1/hate-speech/analyze        → analyze a single text (debug/test)
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.v1.endpoints.auth import _current_user as get_current_user
from app.models.user import UserRecord
from app.schemas.common import ApiResponse
from app.services.social_monitor import CATEGORY_LABELS, social_monitor_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Response schemas ──────────────────────────────────────────────────────────

class SocialPostOut(BaseModel):
    id: str
    platform: str
    author_handle: str
    author_age_days: int | None
    content: str
    language: str
    hate_score: float
    category: str
    category_label: str
    is_flagged: bool
    keyword_matches: list[str]
    model_confidence: float
    like_count: int
    retweet_count: int
    reply_count: int
    engagement_total: int
    posted_at: str
    scraped_at: str
    source_url: str
    hashtags: list[str]
    reviewed: bool
    review_action: str


class HateSpeechStatsOut(BaseModel):
    total_scraped: int
    total_flagged: int
    flagged_last_24h: int
    flagged_last_1h: int
    by_category: dict[str, int]
    by_category_labels: dict[str, str]
    by_language: dict[str, int]
    top_keywords: list[list]
    last_scan_at: str | None
    accounts_flagged: list[str]
    trending_hashtags: list[str] = []
    top_posts_by_engagement: list[str] = []
    hashtag_top_posts: dict[str, list[str]] = {}


class ReplyOut(BaseModel):
    id: str
    author_handle: str
    content: str
    language: str
    like_count: int
    retweet_count: int
    reply_count: int
    engagement_total: int
    posted_at: str
    source_url: str


class AnalyzeRequest(BaseModel):
    text: str


class AnalyzeResponse(BaseModel):
    text: str
    language: str
    hate_score: float
    category: str
    category_label: str
    is_flagged: bool
    keyword_matches: list[str]
    model_confidence: float


class ReviewRequest(BaseModel):
    action: Literal["confirmed", "dismissed"]


# ── Helper ────────────────────────────────────────────────────────────────────

def _post_to_out(post) -> SocialPostOut:  # type: ignore[no-untyped-def]
    return SocialPostOut(
        id=post.id,
        platform=post.platform,
        author_handle=post.author_handle,
        author_age_days=post.author_age_days,
        content=post.content,
        language=post.language,
        hate_score=post.hate_score,
        category=post.category,
        category_label=CATEGORY_LABELS.get(post.category, post.category),
        is_flagged=post.is_flagged,
        keyword_matches=post.keyword_matches,
        model_confidence=post.model_confidence,
        like_count=post.like_count,
        retweet_count=post.retweet_count,
        reply_count=post.reply_count,
        engagement_total=post.engagement_total,
        posted_at=post.posted_at.isoformat(),
        scraped_at=post.scraped_at.isoformat(),
        source_url=post.source_url,
        hashtags=post.hashtags,
        reviewed=post.reviewed,
        review_action=post.review_action,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=ApiResponse[HateSpeechStatsOut])
async def get_hate_speech_stats(
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[HateSpeechStatsOut]:
    """Return aggregated hate speech monitoring statistics."""
    stats = social_monitor_service.get_stats()
    return ApiResponse(data=HateSpeechStatsOut(
        total_scraped=stats.total_scraped,
        total_flagged=stats.total_flagged,
        flagged_last_24h=stats.flagged_last_24h,
        flagged_last_1h=stats.flagged_last_1h,
        by_category=stats.by_category,
        by_category_labels={k: CATEGORY_LABELS.get(k, k) for k in stats.by_category},
        by_language=stats.by_language,
        top_keywords=[list(item) for item in stats.top_keywords],
        last_scan_at=stats.last_scan_at.isoformat() if stats.last_scan_at else None,
        accounts_flagged=stats.accounts_flagged,
        trending_hashtags=stats.trending_hashtags,
        top_posts_by_engagement=stats.top_posts_by_engagement,
        hashtag_top_posts=stats.hashtag_top_posts,
    ))


@router.get("/posts", response_model=ApiResponse[list[SocialPostOut]])
async def list_flagged_posts(
    category: str | None = Query(None),
    min_score: float = Query(51.0, ge=0, le=100),
    reviewed: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[list[SocialPostOut]]:
    """Return paginated list of flagged posts."""
    posts = social_monitor_service.list_flagged(
        limit=limit,
        category=category,
        min_score=min_score,
        reviewed=reviewed,
    )
    return ApiResponse(data=[_post_to_out(p) for p in posts])


@router.get("/all", response_model=ApiResponse[list[SocialPostOut]])
async def list_all_posts(
    hours: int = Query(24, ge=1, le=72),
    limit: int = Query(100, ge=1, le=500),
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[list[SocialPostOut]]:
    """Return all scraped posts (flagged and clean) for the given time window."""
    posts = social_monitor_service.list_all(limit=limit, hours=hours)
    return ApiResponse(data=[_post_to_out(p) for p in posts])


@router.post("/scan", response_model=ApiResponse[dict])
async def trigger_scan(
    include_replies: bool = True,
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[dict]:
    """Manually trigger a scrape + detection cycle."""
    try:
        summary = await social_monitor_service.run_scan(include_replies=include_replies)
        return ApiResponse(data=summary or {"status": "ok"})
    except Exception as exc:
        logger.exception("Manual scan failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/posts/{post_id}/review", response_model=ApiResponse[dict])
async def review_post(
    post_id: str,
    body: ReviewRequest,
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[dict]:
    """Mark a post as reviewed (confirmed hate speech or dismissed false positive)."""
    ok = social_monitor_service.review_post(post_id, body.action)
    if not ok:
        raise HTTPException(status_code=404, detail="Post not found")
    return ApiResponse(data={"post_id": post_id, "action": body.action})


@router.get("/posts/{post_id}/replies", response_model=ApiResponse[list[ReplyOut]])
async def get_post_replies(
    post_id: str,
    limit: int = Query(10, ge=1, le=30),
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[list[ReplyOut]]:
    """Fetch most-liked replies for a post via X TweetDetail API."""
    # post_id format: "x:1234567890"
    tweet_id = post_id.removeprefix("x:")
    try:
        from app.services.x_scraper import x_scraper_service
        raw_replies = await x_scraper_service.fetch_tweet_replies(tweet_id, limit=limit)
    except Exception as exc:
        logger.exception("Failed to fetch replies for %s", post_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    replies = [
        ReplyOut(
            id=f"x:{r.post_id}",
            author_handle=r.author_handle,
            content=r.content,
            language=r.lang,
            like_count=r.like_count,
            retweet_count=r.retweet_count,
            reply_count=r.reply_count,
            engagement_total=r.engagement_total,
            posted_at=r.posted_at.isoformat(),
            source_url=r.source_url,
        )
        for r in raw_replies
    ]
    return ApiResponse(data=replies)


@router.post("/analyze", response_model=ApiResponse[AnalyzeResponse])
async def analyze_text(
    body: AnalyzeRequest,
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[AnalyzeResponse]:
    """Analyze a single piece of text for hate speech (for testing/debug)."""
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty")
    result = await hate_speech_detector.analyze(body.text)  # type: ignore[name-defined]
    return ApiResponse(data=AnalyzeResponse(
        text=result.text,
        language=result.language,
        hate_score=result.hate_score,
        category=result.category,
        category_label=CATEGORY_LABELS.get(result.category, result.category),
        is_flagged=result.is_flagged,
        keyword_matches=result.keyword_matches,
        model_confidence=result.model_confidence,
    ))


# Fix: import detector for the analyze endpoint
from app.services.hate_speech_detector import hate_speech_detector  # noqa: E402
