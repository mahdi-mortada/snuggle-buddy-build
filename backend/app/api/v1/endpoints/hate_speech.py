"""Hate Speech Monitor API Endpoints.

GET  /api/v1/hate-speech/stats              → aggregated statistics + trend clusters
GET  /api/v1/hate-speech/trends             → active trend clusters with risk scores
GET  /api/v1/hate-speech/posts              → flagged post feed (paginated, sortable)
GET  /api/v1/hate-speech/all                → all posts (sortable: priority|score|engagement|velocity|recent)
POST /api/v1/hate-speech/scan               → trigger manual scan
POST /api/v1/hate-speech/posts/{id}/review  → mark post reviewed
GET  /api/v1/hate-speech/posts/{id}/replies → most-liked replies
POST /api/v1/hate-speech/analyze            → analyze a single text (debug/test)
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.v1.endpoints.auth import _current_user as get_current_user
from app.models.user import UserRecord
from app.schemas.common import ApiResponse
from app.services.social_monitor import CATEGORY_LABELS, TrendCluster, social_monitor_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Response schemas ───────────────────────────────────────────────────────────

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
    # Trend-first fields
    matched_trend: str
    engagement_velocity: float
    priority_score: float


class TrendClusterOut(BaseModel):
    trend: str
    display_name: str
    tweet_volume: int | None
    trend_rank: int
    post_count: int
    flagged_count: int
    avg_risk_score: float
    max_risk_score: float
    total_engagement: int
    top_post_ids: list[str]
    source: str
    # Derived
    flag_rate: float         # flagged_count / post_count
    risk_level: str          # "critical" | "high" | "medium" | "low"


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
    active_trends: list[TrendClusterOut] = []


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


class AgentStatusOut(BaseModel):
    mode: str
    is_running: bool
    scan_count: int
    total_posts_discovered: int
    last_scan_at: str | None
    last_scan_duration_seconds: float
    last_scan_posts_found: int
    next_scan_at: str | None
    sources_last_scan: list[str]
    queries_used: int
    discovery_strategies: list[str]
    scan_interval_seconds: int
    current_posts_in_store: int
    description: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _risk_level(max_score: float) -> str:
    if max_score >= 80:
        return "critical"
    if max_score >= 60:
        return "high"
    if max_score >= 40:
        return "medium"
    return "low"


def _cluster_to_out(c: TrendCluster) -> TrendClusterOut:
    flag_rate = round(c.flagged_count / max(1, c.post_count), 3)
    return TrendClusterOut(
        trend=c.trend,
        display_name=c.display_name,
        tweet_volume=c.tweet_volume,
        trend_rank=c.trend_rank,
        post_count=c.post_count,
        flagged_count=c.flagged_count,
        avg_risk_score=c.avg_risk_score,
        max_risk_score=c.max_risk_score,
        total_engagement=c.total_engagement,
        top_post_ids=c.top_post_ids,
        source=c.source,
        flag_rate=flag_rate,
        risk_level=_risk_level(c.max_risk_score),
    )


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
        matched_trend=post.matched_trend,
        engagement_velocity=round(post.engagement_velocity, 2),
        priority_score=round(post.priority_score, 1),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=ApiResponse[HateSpeechStatsOut])
async def get_hate_speech_stats(
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[HateSpeechStatsOut]:
    """Return aggregated statistics + active trend cluster summaries."""
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
        active_trends=[_cluster_to_out(c) for c in stats.active_trends],
    ))


@router.get("/trends", response_model=ApiResponse[list[TrendClusterOut]])
async def get_trend_clusters(
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[list[TrendClusterOut]]:
    """Return active Lebanon trend clusters sorted by risk (highest risk first).

    Each cluster includes:
      - trend name and rank in Lebanon trends
      - post count, flagged count, flag rate
      - avg/max risk score
      - risk_level label (critical/high/medium/low)
      - total engagement and top post IDs
    """
    stats = social_monitor_service.get_stats()
    return ApiResponse(data=[_cluster_to_out(c) for c in stats.active_trends])


@router.get("/posts", response_model=ApiResponse[list[SocialPostOut]])
async def list_flagged_posts(
    category: str | None = Query(None),
    min_score: float = Query(51.0, ge=0, le=100),
    reviewed: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("priority", pattern="^(priority|score|engagement|velocity|recent)$"),
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[list[SocialPostOut]]:
    """Return paginated list of flagged posts.

    sort options: priority (default), score, engagement, velocity, recent
    """
    posts = social_monitor_service.list_flagged(
        limit=limit,
        category=category,
        min_score=min_score,
        reviewed=reviewed,
        sort=sort,
    )
    return ApiResponse(data=[_post_to_out(p) for p in posts])


@router.get("/all", response_model=ApiResponse[list[SocialPostOut]])
async def list_all_posts(
    hours: int = Query(24, ge=1, le=72),
    limit: int = Query(100, ge=1, le=500),
    sort: str = Query("priority", pattern="^(priority|score|engagement|velocity|recent)$"),
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[list[SocialPostOut]]:
    """Return all scraped posts (flagged and clean) sorted by priority by default."""
    posts = social_monitor_service.list_all(limit=limit, hours=hours, sort=sort)
    return ApiResponse(data=[_post_to_out(p) for p in posts])


@router.get("/trend/{trend_name}", response_model=ApiResponse[list[SocialPostOut]])
async def list_posts_by_trend(
    trend_name: str,
    limit: int = Query(20, ge=1, le=100),
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[list[SocialPostOut]]:
    """Return posts for a specific trend, sorted by priority score."""
    posts = social_monitor_service.list_by_trend(trend_name, limit=limit)
    return ApiResponse(data=[_post_to_out(p) for p in posts])


@router.post("/scan", response_model=ApiResponse[dict])
async def trigger_scan(
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[dict]:
    """Manually trigger a trend discovery → scrape → detection cycle."""
    try:
        summary = await social_monitor_service.run_scan()
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
    """Fetch most-liked replies for a post via X TweetDetail GraphQL."""
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


@router.get("/search", response_model=ApiResponse[list[SocialPostOut]])
async def search_hashtag_live(
    q: str = Query(..., min_length=1, description="Arabic hashtag or keyword (with or without #)"),
    limit: int = Query(10, ge=1, le=20),
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[list[SocialPostOut]]:
    """Search for real public X posts about a hashtag via SearchTimeline GraphQL.

    Priority order:
      1. Authenticated SearchTimeline (most-interacted Arabic posts from all of X)
      2. Guest token search (fallback, limited for Arabic)
      3. Agent's collected store (last resort)

    Results are sorted by total engagement (likes + retweets + replies + quotes).
    Hate speech analysis is run on each result in real time.
    """
    from datetime import UTC, datetime as _datetime
    from app.services.x_scraper import x_scraper_service, TrendTopic as _TrendTopic
    from app.services.social_monitor import SocialPost, _compute_priority

    # Normalise: strip leading # so we can build both forms
    query_clean = q.strip().lstrip("#")

    try:
        raw_posts: list = []

        # ── Stage 1: Authenticated SearchTimeline (works for Arabic without phone-verify) ──
        synthetic_trend = _TrendTopic(
            name=query_clean,
            display_name=f"#{query_clean}",
            tweet_volume=None,
            trend_rank=1,
            source="user_search",
        )
        raw_posts = await x_scraper_service._twscrape.search_hashtag_top(
            synthetic_trend, limit=min(limit * 3, 40)
        )
        if raw_posts:
            logger.info("Hashtag search #%s — SearchTimeline → %d posts", query_clean, len(raw_posts))

        # ── Stage 2: Guest token fallback (for English/short queries) ──
        if not raw_posts:
            raw_posts = await x_scraper_service._guest.search(f"#{query_clean}", limit=min(limit * 3, 60))
            if raw_posts:
                logger.info("Hashtag search #%s — guest API → %d posts", query_clean, len(raw_posts))

        # Sort by total engagement and trim to requested limit
        raw_posts.sort(key=lambda p: p.engagement_total, reverse=True)
        raw_posts = raw_posts[:limit]

        if not raw_posts:
            # ── Stage 3: Stored agent posts (real data already collected) ──
            stored = social_monitor_service.search_posts(query_clean, limit=limit)
            logger.info(
                "Hashtag search #%s — live API returned 0, found %d in agent store",
                query_clean, len(stored),
            )
            return ApiResponse(data=[_post_to_out(p) for p in stored])

        # Run hate speech detection + build SocialPost objects for live results
        results: list[SocialPostOut] = []
        for raw in raw_posts:
            try:
                det = await hate_speech_detector.analyze(raw.content)
                raw.compute_engagement_velocity()
                hate_score = det.hate_score
                priority = _compute_priority(
                    hate_score, raw.engagement_velocity, 99, raw.account_age_days
                )
                post = SocialPost(
                    id=f"x:{raw.post_id}",
                    platform="x",
                    author_handle=raw.author_handle,
                    author_id=raw.author_id,
                    author_age_days=raw.account_age_days,
                    content=raw.content,
                    language=det.language,
                    hate_score=hate_score,
                    category=det.category,
                    is_flagged=hate_score >= 51.0,
                    keyword_matches=det.keyword_matches,
                    model_confidence=det.model_confidence,
                    like_count=raw.like_count,
                    retweet_count=raw.retweet_count,
                    reply_count=raw.reply_count,
                    quote_count=raw.quote_count,
                    engagement_total=raw.engagement_total,
                    posted_at=raw.posted_at,
                    scraped_at=_datetime.now(UTC),
                    source_url=raw.source_url,
                    hashtags=raw.hashtags,
                    matched_trend=query_clean,
                    engagement_velocity=raw.engagement_velocity,
                    priority_score=priority,
                )
                results.append(_post_to_out(post))
            except Exception as exc:
                logger.debug("Search result skipped for %s: %s", raw.post_id, exc)
                continue

        logger.info("Hashtag search #%s (live) → %d results", query_clean, len(results))
        return ApiResponse(data=results)

    except Exception as exc:
        logger.exception("Hashtag search failed for query=%s", q)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/agent-status", response_model=ApiResponse[AgentStatusOut])
async def get_agent_status(
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[AgentStatusOut]:
    """Return public discovery agent status — mode, last scan, next scan, strategies used."""
    data = social_monitor_service.get_agent_status()
    return ApiResponse(data=AgentStatusOut(**data))


@router.post("/analyze", response_model=ApiResponse[AnalyzeResponse])
async def analyze_text(
    body: AnalyzeRequest,
    _user: UserRecord = Depends(get_current_user),
) -> ApiResponse[AnalyzeResponse]:
    """Analyze a single piece of text for hate speech (for testing/debug)."""
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty")
    result = await hate_speech_detector.analyze(body.text)
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


from app.services.hate_speech_detector import hate_speech_detector  # noqa: E402
