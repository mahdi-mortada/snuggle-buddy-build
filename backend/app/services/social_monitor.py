"""Social Media Hate Speech Monitor Service — Trend-First Architecture.

Orchestrates the full pipeline:
  1. Discover Lebanon trending topics (via x_scraper_service.discover_trends)
  2. Scrape top tweets for each trend
  3. Run hate_speech_detector on each tweet
  4. Compute priority_score = 0.55 * hate_score + 0.30 * velocity_score + 0.15 * trend_rank_score
  5. Store enriched posts in memory (+ pruned at 72h)
  6. Expose stats, trend clusters, and ranked post feed via the API

Priority score combines:
  - hate_score          (0–100): how hateful/risky the content is
  - engagement_velocity (0–100): engagement per hour (virality/traction signal)
  - trend_rank_score    (0–100): how prominently the topic is trending in Lebanon

This allows surfacing: tweets that are BOTH spreading fast AND risky.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.services.hate_speech_detector import HateSpeechResult, hate_speech_detector
from app.services.x_scraper import PUBLIC_HATE_SPEECH_QUERIES, ScrapedPost, TrendTopic, x_scraper_service

logger = logging.getLogger(__name__)

HateSpeechCategory = Literal["sectarian", "anti_refugee", "political_incite", "misogynistic", "clean"]

CATEGORY_LABELS: dict[str, str] = {
    "sectarian": "Sectarian Hate",
    "anti_refugee": "Anti-Refugee",
    "political_incite": "Political Incitement",
    "misogynistic": "Misogynistic",
    "clean": "Clean",
}


@dataclass
class SocialPost:
    """Enriched tweet with hate speech analysis + priority scoring."""
    id: str                        # "x:{tweet_id}"
    platform: str                  # "x"
    author_handle: str
    author_id: str
    author_age_days: int | None
    content: str
    language: str
    hate_score: float              # 0–100
    category: str
    is_flagged: bool
    keyword_matches: list[str]
    model_confidence: float
    like_count: int
    retweet_count: int
    reply_count: int
    quote_count: int
    engagement_total: int
    posted_at: datetime
    scraped_at: datetime
    source_url: str
    hashtags: list[str]
    # Trend-first fields
    matched_trend: str = ""           # which trend this post was found under
    engagement_velocity: float = 0.0  # engagement per hour (virality signal)
    priority_score: float = 0.0       # combined score for surfacing risky viral posts
    # Review fields
    reviewed: bool = False
    review_action: str = ""            # "confirmed" | "dismissed" | ""


@dataclass
class TrendCluster:
    """Aggregated risk stats for a trending topic."""
    trend: str                     # hashtag name (no #)
    display_name: str              # with # prefix
    tweet_volume: int | None       # from X trends API
    trend_rank: int
    post_count: int
    flagged_count: int
    avg_risk_score: float
    max_risk_score: float
    total_engagement: int
    top_post_ids: list[str]        # top 5 by priority_score
    source: str                    # "x_api" | "curated"


@dataclass
class HateSpeechStats:
    total_scraped: int = 0
    total_flagged: int = 0
    flagged_last_24h: int = 0
    flagged_last_1h: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_language: dict[str, int] = field(default_factory=dict)
    top_keywords: list[tuple[str, int]] = field(default_factory=list)
    last_scan_at: datetime | None = None
    accounts_flagged: list[str] = field(default_factory=list)
    trending_hashtags: list[str] = field(default_factory=list)
    top_posts_by_engagement: list[str] = field(default_factory=list)
    hashtag_top_posts: dict[str, list[str]] = field(default_factory=dict)
    # New: trend cluster summaries
    active_trends: list[TrendCluster] = field(default_factory=list)


@dataclass
class AgentStatus:
    """Real-time status of the public discovery agent.

    Tracks what the autonomous scanning agent is doing, what strategies it used,
    and when the next scan is scheduled — so the UI can show agent activity
    instead of a manual 'Scan Now' button.
    """
    mode: str = "public_discovery"         # discovery mode label
    is_running: bool = False               # True during active scan
    scan_count: int = 0                    # total scans completed since startup
    total_posts_discovered: int = 0        # cumulative unique posts stored
    last_scan_at: datetime | None = None
    last_scan_duration_seconds: float = 0.0
    last_scan_posts_found: int = 0         # posts analyzed in the last scan
    next_scan_at: datetime | None = None
    sources_last_scan: list[str] = field(default_factory=list)
    queries_used: int = 0
    discovery_strategies: list[str] = field(default_factory=list)
    scan_interval_seconds: int = 1800      # matches Celery beat (30 min)


# ── Demo posts ─────────────────────────────────────────────────────────────────
# (handle, lang, content, kw_matches, category, score, hashtags, likes, rts, replies, trend)


def _compute_priority(
    hate_score: float,
    engagement_velocity: float,
    trend_rank: int,
    author_age_days: int | None,
) -> float:
    """Compute priority score for surfacing risky + viral posts.

    Formula:
      priority = 0.55 * hate_score
               + 0.30 * min(100, engagement_velocity)
               + 0.15 * trend_rank_score

    trend_rank_score = max(0, 100 - (rank - 1) * 10)
      → rank 1 = 100, rank 2 = 90, ..., rank 10 = 10, rank 11+ = 0

    Bonus: new account (< 30 days) with high hate score gets +5
    """
    trend_rank_score = max(0.0, 100.0 - (trend_rank - 1) * 10.0)
    velocity_score = min(100.0, engagement_velocity)

    score = (
        0.55 * hate_score
        + 0.30 * velocity_score
        + 0.15 * trend_rank_score
    )

    if author_age_days is not None and author_age_days < 30 and hate_score >= 50:
        score = min(100.0, score + 5.0)

    return round(score, 1)


class SocialMonitorService:
    """In-memory store + trend-first pipeline orchestrator."""

    def __init__(self) -> None:
        self._posts: dict[str, SocialPost] = {}
        self._is_running = False
        self._scan_interval_seconds = 1800   # 30 minutes

        self._last_trend_map: dict[str, TrendTopic] = {}  # trend.name → TrendTopic
        self._agent_status = AgentStatus(
            scan_interval_seconds=self._scan_interval_seconds,
            queries_used=len(PUBLIC_HATE_SPEECH_QUERIES),
        )

    # ── Pipeline ──────────────────────────────────────────────────────────────

    async def run_scan(self, include_replies: bool = True) -> dict[str, int]:
        """Run a full public-discovery → scrape → detect → score cycle.

        Discovery pipeline (each stage only runs if previous returned < 30 posts):
          1. Lebanon trend discovery → authenticated SearchTimeline per trend
          2. Public keyword scan via guest token API (no account — truly public)
          3. Seed keyword queries (authenticated SearchTimeline + guest fallback)

        Account-based timeline scraping (14 fixed accounts) is intentionally
        removed from the pipeline. Discovery is now fully public.

        Returns summary counts: {scraped, analyzed, flagged}.
        """
        scan_start = time.monotonic()
        logger.info("Social monitor: starting public discovery scan")
        scraped: list[ScrapedPost] = []
        trends: list[TrendTopic] = []
        sources_used: list[str] = []
        strategies_used: list[str] = []

        self._agent_status.is_running = True

        # ── Stage 1: Lebanon trend discovery → authenticated SearchTimeline ──
        try:
            trends = await x_scraper_service.discover_trends(max_trends=15)
            # Update local trend map for priority scoring
            self._last_trend_map = {t.name.lower(): t for t in trends}

            trending_posts = await x_scraper_service.scrape_for_trends(
                trends, tweets_per_trend=20, use_account_fallback=False
            )
            if trending_posts:
                logger.info("Trend-first scrape: %d posts from %d trends", len(trending_posts), len(trends))
                scraped.extend(trending_posts)
                sources_used.append("trend_search")
                strategies_used.append("authenticated_trend_search")
        except Exception as exc:
            logger.warning("Trend-first scrape failed: %s", exc)

        # ── Stage 2: Public keyword scan via guest API (no account needed) ──
        # This is the PRIMARY public fallback. Searches ALL public X posts,
        # not restricted to any specific accounts.
        if len(scraped) < 30:
            try:
                public_posts = await x_scraper_service.scrape_public_keywords()
                if public_posts:
                    logger.info("Public keyword scan: %d posts (guest API, no account)", len(public_posts))
                    scraped.extend(public_posts)
                    sources_used.append("public_keyword_search")
                    strategies_used.append("guest_api_keyword_scan")
            except Exception as exc:
                logger.warning("Public keyword scan failed: %s", exc)

        # ── Stage 3: Curated seed queries (authenticated + guest fallback) ──
        if len(scraped) < 20:
            try:
                query_posts = await x_scraper_service.scrape_queries()
                if query_posts:
                    scraped.extend(query_posts)
                    sources_used.append("curated_queries")
                    strategies_used.append("seed_query_search")
            except Exception as exc:
                logger.warning("Query scrape fallback failed: %s", exc)

        # ── Stage 4: Lebanese media account timelines (reliable fallback) ──
        # Uses UserTweets GraphQL (different from SearchTimeline — not blocked).
        # Provides real Arabic/French content from verified Lebanese sources.
        # Only runs when all public-discovery stages return too few posts.
        if len(scraped) < 20:
            try:
                account_posts = await x_scraper_service.scrape_media_timelines(
                    limit_per_account=30, min_engagement=0, max_age_hours=48
                )
                if account_posts:
                    # Tag each post with best matching trend from content
                    for p in account_posts:
                        if not p.matched_trend:
                            p.matched_trend = "لبنان"
                        p.compute_engagement_velocity()
                    logger.info("Account timeline fallback: %d posts from Lebanese media", len(account_posts))
                    scraped.extend(account_posts)
                    sources_used.append("lebanese_media_accounts")
                    strategies_used.append("account_timeline_fallback")
            except Exception as exc:
                logger.warning("Account timeline fallback failed: %s", exc)

        # ── Filter: Arabic only ──────────────────────────────────────────────────
        # X sets lang="ar" for Arabic tweets. Accept lang="" (unknown) too since
        # the guest API sometimes omits the field. Drop all other languages.
        arabic_only = [r for r in scraped if r.lang in ("ar", "")]
        non_arabic = len(scraped) - len(arabic_only)
        if non_arabic:
            logger.info("Language filter: dropped %d non-Arabic posts (kept %d Arabic)", non_arabic, len(arabic_only))
        scraped = arabic_only

        if not scraped:
            logger.info("No Arabic posts scraped — nothing to analyze")
            self._agent_status.is_running = False
            self._agent_status.scan_count += 1
            self._agent_status.last_scan_at = datetime.now(UTC)
            self._agent_status.last_scan_duration_seconds = round(time.monotonic() - scan_start, 1)
            self._agent_status.last_scan_posts_found = 0
            self._agent_status.sources_last_scan = sources_used
            self._agent_status.discovery_strategies = strategies_used
            self._agent_status.queries_used = len(PUBLIC_HATE_SPEECH_QUERIES)
            self._agent_status.next_scan_at = datetime.now(UTC) + timedelta(seconds=self._scan_interval_seconds)
            return {"scraped": 0, "analyzed": 0, "flagged": sum(
                1 for p in self._posts.values() if p.is_flagged
            )}

        # ── Drop posts older than 48 hours (timeline scraping can return stale content) ──
        now = datetime.now(UTC)
        max_post_age = timedelta(hours=48)
        fresh_scraped = [r for r in scraped if (now - r.posted_at) <= max_post_age]
        stale_count = len(scraped) - len(fresh_scraped)
        if stale_count:
            logger.info("Dropped %d stale posts (>48h old) — keeping %d fresh posts", stale_count, len(fresh_scraped))
        scraped = fresh_scraped

        if not scraped:
            logger.info("All scraped posts were stale (>48h) — no new content to analyze")
            return {"scraped": 0, "analyzed": 0, "flagged": sum(
                1 for p in self._posts.values() if p.is_flagged
            )}

        # ── Stage 3: Hate speech detection ──
        analyzed = 0
        flagged = 0

        for raw in scraped:
            post_id = f"x:{raw.post_id}"
            if post_id in self._posts:
                # Update engagement metrics for already-seen posts
                existing = self._posts[post_id]
                existing.like_count = raw.like_count
                existing.retweet_count = raw.retweet_count
                existing.reply_count = raw.reply_count
                existing.quote_count = raw.quote_count
                existing.engagement_total = raw.engagement_total
                existing.engagement_velocity = raw.engagement_velocity
                # Re-score priority with fresh engagement
                trend_obj = self._last_trend_map.get(existing.matched_trend.lower())
                trend_rank = trend_obj.trend_rank if trend_obj else 99
                existing.priority_score = _compute_priority(
                    existing.hate_score,
                    raw.engagement_velocity,
                    trend_rank,
                    existing.author_age_days,
                )
                continue

            try:
                result: HateSpeechResult = await hate_speech_detector.analyze(raw.content)
            except Exception as exc:
                logger.debug("Detector failed for %s: %s", raw.post_id, exc)
                continue

            # Find trend rank for priority scoring
            trend_obj = self._last_trend_map.get(raw.matched_trend.lower())
            trend_rank = trend_obj.trend_rank if trend_obj else 99

            # New-account suspicion boost
            hate_score = result.hate_score
            if raw.account_age_days is not None and raw.account_age_days < 30:
                hate_score = min(100.0, hate_score * 1.2)

            is_flagged = hate_score >= 51.0

            priority = _compute_priority(
                hate_score,
                raw.engagement_velocity,
                trend_rank,
                raw.account_age_days,
            )

            post = SocialPost(
                id=post_id,
                platform=raw.platform,
                author_handle=raw.author_handle,
                author_id=raw.author_id,
                author_age_days=raw.account_age_days,
                content=raw.content,
                language=result.language,
                hate_score=hate_score,
                category=result.category,
                is_flagged=is_flagged,
                keyword_matches=result.keyword_matches,
                model_confidence=result.model_confidence,
                like_count=raw.like_count,
                retweet_count=raw.retweet_count,
                reply_count=raw.reply_count,
                quote_count=raw.quote_count,
                engagement_total=raw.engagement_total,
                posted_at=raw.posted_at,
                scraped_at=datetime.now(UTC),
                source_url=raw.source_url,
                hashtags=raw.hashtags,
                matched_trend=raw.matched_trend,
                engagement_velocity=raw.engagement_velocity,
                priority_score=priority,
            )

            self._posts[post_id] = post
            analyzed += 1
            if is_flagged:
                flagged += 1

        # Prune old entries (keep last 72h by posted_at)
        cutoff = datetime.now(UTC) - timedelta(hours=72)
        self._posts = {k: v for k, v in self._posts.items() if v.posted_at >= cutoff}

        logger.info(
            "Social monitor scan: scraped=%d analyzed=%d flagged=%d trends=%d strategies=%s",
            len(scraped), analyzed, flagged, len(trends), strategies_used,
        )

        # ── Update agent status ──
        now = datetime.now(UTC)
        self._agent_status.is_running = False
        self._agent_status.scan_count += 1
        self._agent_status.last_scan_at = now
        self._agent_status.last_scan_duration_seconds = round(time.monotonic() - scan_start, 1)
        self._agent_status.last_scan_posts_found = analyzed
        self._agent_status.total_posts_discovered += analyzed
        self._agent_status.sources_last_scan = sources_used
        self._agent_status.discovery_strategies = strategies_used
        self._agent_status.queries_used = len(PUBLIC_HATE_SPEECH_QUERIES)
        self._agent_status.next_scan_at = now + timedelta(seconds=self._scan_interval_seconds)

        return {"scraped": len(scraped), "analyzed": analyzed, "flagged": flagged}

    # ── Background loop ───────────────────────────────────────────────────────

    async def start_background_loop(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        asyncio.create_task(self._loop())
        logger.info("Social monitor background loop started (interval=%ds)", self._scan_interval_seconds)

    async def _loop(self) -> None:
        await asyncio.sleep(30)
        while True:
            try:
                await self.run_scan()
            except Exception as exc:
                logger.warning("Social monitor loop error: %s", exc)
            await asyncio.sleep(self._scan_interval_seconds)

    # ── Query helpers ─────────────────────────────────────────────────────────

    def list_flagged(
        self,
        limit: int = 50,
        category: str | None = None,
        min_score: float = 51.0,
        reviewed: bool | None = None,
        sort: str = "priority",
    ) -> list[SocialPost]:
        posts = [
            p for p in self._posts.values()
            if p.hate_score >= min_score
            and (category is None or p.category == category)
            and (reviewed is None or p.reviewed == reviewed)
        ]
        return self._sort_posts(posts, sort)[:limit]

    def list_all(
        self,
        limit: int = 100,
        hours: int = 24,
        sort: str = "priority",
    ) -> list[SocialPost]:
        # Filter by scraped_at (when WE collected it) not posted_at.
        # Account timeline posts may be 24-48h old but were scraped moments ago,
        # so filtering by posted_at would hide them. scraped_at is always recent.
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        posts = [p for p in self._posts.values() if p.scraped_at >= cutoff]
        return self._sort_posts(posts, sort)[:limit]

    def list_by_trend(self, trend_name: str, limit: int = 20) -> list[SocialPost]:
        """Return posts for a specific trend, sorted by priority."""
        posts = [
            p for p in self._posts.values()
            if p.matched_trend.lower() == trend_name.lower()
        ]
        return self._sort_posts(posts, "priority")[:limit]

    def _sort_posts(self, posts: list[SocialPost], sort: str) -> list[SocialPost]:
        if sort == "priority":
            return sorted(posts, key=lambda p: p.priority_score, reverse=True)
        if sort == "score":
            return sorted(posts, key=lambda p: p.hate_score, reverse=True)
        if sort == "engagement":
            return sorted(posts, key=lambda p: p.engagement_total, reverse=True)
        if sort == "velocity":
            return sorted(posts, key=lambda p: p.engagement_velocity, reverse=True)
        # default: recent
        return sorted(posts, key=lambda p: p.scraped_at, reverse=True)

    def get_stats(self) -> HateSpeechStats:
        now = datetime.now(UTC)
        cutoff_24h = now - timedelta(hours=24)
        cutoff_1h = now - timedelta(hours=1)

        all_posts = list(self._posts.values())
        flagged = [p for p in all_posts if p.is_flagged]

        by_cat: dict[str, int] = {}
        for p in all_posts:
            by_cat[p.category] = by_cat.get(p.category, 0) + 1

        by_lang: dict[str, int] = {}
        for p in all_posts:
            by_lang[p.language] = by_lang.get(p.language, 0) + 1

        kw_freq: dict[str, int] = {}
        for p in flagged:
            for kw in p.keyword_matches:
                kw_freq[kw] = kw_freq.get(kw, 0) + 1
        top_kw = sorted(kw_freq.items(), key=lambda x: x[1], reverse=True)[:10]

        acct_freq: dict[str, int] = {}
        for p in flagged:
            if p.author_handle:
                acct_freq[p.author_handle] = acct_freq.get(p.author_handle, 0) + 1
        top_accounts = [h for h, _ in sorted(acct_freq.items(), key=lambda x: x[1], reverse=True)[:5]]

        last_scan: datetime | None = max((p.scraped_at for p in all_posts), default=None)

        # Trending hashtags (from post hashtag engagement)
        hashtag_engagement: dict[str, int] = {}
        hashtag_posts: dict[str, list[SocialPost]] = {}
        for p in all_posts:
            for tag in p.hashtags:
                if tag:
                    hashtag_engagement[tag] = hashtag_engagement.get(tag, 0) + p.engagement_total + 1
                    hashtag_posts.setdefault(tag, []).append(p)

        trending = [tag for tag, _ in sorted(hashtag_engagement.items(), key=lambda x: x[1], reverse=True)[:15]]

        # Hashtag → top-5 post IDs by priority_score
        hashtag_top: dict[str, list[str]] = {}
        for tag in trending:
            posts_for_tag = sorted(
                hashtag_posts.get(tag, []),
                key=lambda p: p.priority_score,
                reverse=True,
            )
            hashtag_top[tag] = [p.id for p in posts_for_tag[:5]]

        # Top posts by engagement
        sorted_by_eng = sorted(all_posts, key=lambda p: p.engagement_total, reverse=True)
        top_eng_ids = [p.id for p in sorted_by_eng[:10]]

        # ── Build trend cluster summaries ──
        active_trends = self._build_trend_clusters(all_posts)

        return HateSpeechStats(
            total_scraped=len(all_posts),
            total_flagged=len(flagged),
            flagged_last_24h=sum(1 for p in flagged if p.scraped_at >= cutoff_24h),
            flagged_last_1h=sum(1 for p in flagged if p.scraped_at >= cutoff_1h),
            by_category=by_cat,
            by_language=by_lang,
            top_keywords=top_kw,
            last_scan_at=last_scan,
            accounts_flagged=top_accounts,
            trending_hashtags=trending,
            top_posts_by_engagement=top_eng_ids,
            hashtag_top_posts=hashtag_top,
            active_trends=active_trends,
        )

    def _build_trend_clusters(self, all_posts: list[SocialPost]) -> list[TrendCluster]:
        """Group posts by matched_trend and compute risk/engagement stats per cluster."""
        cluster_posts: dict[str, list[SocialPost]] = {}
        for p in all_posts:
            if p.matched_trend:
                cluster_posts.setdefault(p.matched_trend, []).append(p)

        clusters: list[TrendCluster] = []
        for trend_name, posts in cluster_posts.items():
            flagged = [p for p in posts if p.is_flagged]
            top_posts = sorted(posts, key=lambda p: p.priority_score, reverse=True)[:5]
            avg_risk = sum(p.hate_score for p in posts) / len(posts) if posts else 0.0
            max_risk = max((p.hate_score for p in posts), default=0.0)
            total_eng = sum(p.engagement_total for p in posts)

            # Get trend metadata from the last known trends
            trend_obj = self._last_trend_map.get(trend_name.lower())
            trend_rank = trend_obj.trend_rank if trend_obj else 99
            tweet_volume = trend_obj.tweet_volume if trend_obj else None
            source = trend_obj.source if trend_obj else "unknown"

            clusters.append(TrendCluster(
                trend=trend_name,
                display_name=f"#{trend_name}",
                tweet_volume=tweet_volume,
                trend_rank=trend_rank,
                post_count=len(posts),
                flagged_count=len(flagged),
                avg_risk_score=round(avg_risk, 1),
                max_risk_score=round(max_risk, 1),
                total_engagement=total_eng,
                top_post_ids=[p.id for p in top_posts],
                source=source,
            ))

        # Sort clusters by: max_risk_score desc, then total_engagement desc
        clusters.sort(key=lambda c: (c.max_risk_score, c.total_engagement), reverse=True)
        return clusters[:20]

    def search_posts(self, query: str, limit: int = 10) -> list[SocialPost]:
        """Search stored posts by hashtag match or content keyword.

        Used as a fallback when the live X guest API is unavailable.
        Returns real posts collected by the agent, sorted by engagement total.
        """
        q = query.lower().lstrip("#").strip()
        if not q:
            return []
        matches = [
            p for p in self._posts.values()
            if any(q in tag.lower() for tag in p.hashtags)
            or q in p.content.lower()
        ]
        return sorted(matches, key=lambda p: p.engagement_total, reverse=True)[:limit]

    def review_post(self, post_id: str, action: str) -> bool:
        """Mark a post as reviewed. action: 'confirmed' | 'dismissed'."""
        post = self._posts.get(post_id)
        if not post:
            return False
        post.reviewed = True
        post.review_action = action
        return True

    def get_agent_status(self) -> dict:
        """Return the current public discovery agent status as a plain dict."""
        s = self._agent_status
        return {
            "mode": s.mode,
            "is_running": s.is_running,
            "scan_count": s.scan_count,
            "total_posts_discovered": s.total_posts_discovered,
            "last_scan_at": s.last_scan_at.isoformat() if s.last_scan_at else None,
            "last_scan_duration_seconds": s.last_scan_duration_seconds,
            "last_scan_posts_found": s.last_scan_posts_found,
            "next_scan_at": s.next_scan_at.isoformat() if s.next_scan_at else None,
            "sources_last_scan": s.sources_last_scan,
            "queries_used": s.queries_used,
            "discovery_strategies": s.discovery_strategies,
            "scan_interval_seconds": s.scan_interval_seconds,
            "current_posts_in_store": len(self._posts),
            "description": (
                "Public Discovery Agent — searches all public X posts using "
                f"{s.queries_used} keyword queries across Arabic, English, and French. "
                "Not restricted to specific accounts."
            ),
        }


social_monitor_service = SocialMonitorService()
