"""Social Media Hate Speech Monitor Service.

Orchestrates the full pipeline:
  1. Scrape X posts via x_scraper_service
  2. Run hate_speech_detector on each post
  3. Store results in memory (+ PostgreSQL when STORAGE_MODE=postgres)
  4. Expose aggregated stats and flagged post feed

In-memory store mirrors the pattern used by local_store.py so the
feature works in both local and postgres modes.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.services.hate_speech_detector import HateSpeechResult, hate_speech_detector
from app.services.x_scraper import ScrapedPost, x_scraper_service

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
    """Fully enriched social post with hate speech analysis."""
    id: str                                   # platform:post_id
    platform: str                             # 'x'
    author_handle: str
    author_id: str
    author_age_days: int | None
    content: str
    language: str
    hate_score: float                         # 0–100
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
    reviewed: bool = False
    review_action: str = ""                   # 'confirmed' | 'dismissed' | ''


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


class SocialMonitorService:
    """In-memory store + pipeline orchestrator for hate speech monitoring."""

    def __init__(self) -> None:
        self._posts: dict[str, SocialPost] = {}   # id → SocialPost
        self._is_running = False
        self._scan_interval_seconds = 1800         # 30 minutes

    # ── Pipeline ──────────────────────────────────────────────────────────────

    async def run_scan(self, include_replies: bool = True) -> dict[str, int]:
        """Run a full scrape + detection cycle. Returns summary counts."""
        logger.info("Social monitor: starting X scan")
        scraped: list[ScrapedPost] = []

        try:
            # Scrape seed queries
            query_posts = await x_scraper_service.scrape_queries()
            scraped.extend(query_posts)
        except Exception as exc:
            logger.warning("Query scrape failed: %s", exc)

        if include_replies:
            try:
                reply_posts = await x_scraper_service.scrape_media_replies()
                scraped.extend(reply_posts)
            except Exception as exc:
                logger.warning("Reply scrape failed: %s", exc)

        analyzed = 0
        flagged = 0

        for raw in scraped:
            post_id = f"x:{raw.post_id}"
            if post_id in self._posts:
                continue  # Already processed

            try:
                result: HateSpeechResult = await hate_speech_detector.analyze(raw.content)
            except Exception as exc:
                logger.debug("Detector failed for %s: %s", raw.post_id, exc)
                continue

            post = SocialPost(
                id=post_id,
                platform=raw.platform,
                author_handle=raw.author_handle,
                author_id=raw.author_id,
                author_age_days=raw.account_age_days,
                content=raw.content,
                language=result.language,
                hate_score=result.hate_score,
                category=result.category,
                is_flagged=result.is_flagged,
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
            )

            # Context multiplier: new account + high engagement = higher suspicion
            if post.author_age_days is not None and post.author_age_days < 30:
                post.hate_score = min(100.0, post.hate_score * 1.2)
                if post.hate_score >= 51.0:
                    post.is_flagged = True

            self._posts[post_id] = post
            analyzed += 1
            if post.is_flagged:
                flagged += 1

        # Prune old entries (keep last 72h)
        cutoff = datetime.now(UTC) - timedelta(hours=72)
        self._posts = {
            k: v for k, v in self._posts.items()
            if v.scraped_at >= cutoff
        }

        logger.info("Social monitor scan: scraped=%d analyzed=%d flagged=%d", len(scraped), analyzed, flagged)
        return {"scraped": len(scraped), "analyzed": analyzed, "flagged": flagged}

    # ── Background loop ───────────────────────────────────────────────────────

    async def start_background_loop(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        asyncio.create_task(self._loop())
        logger.info("Social monitor background loop started (interval=%ds)", self._scan_interval_seconds)

    async def _loop(self) -> None:
        # First scan after a short delay to let the app fully start
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
    ) -> list[SocialPost]:
        posts = [
            p for p in self._posts.values()
            if p.hate_score >= min_score
            and (category is None or p.category == category)
            and (reviewed is None or p.reviewed == reviewed)
        ]
        posts.sort(key=lambda p: p.hate_score, reverse=True)
        return posts[:limit]

    def list_all(self, limit: int = 100, hours: int = 24) -> list[SocialPost]:
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        posts = [p for p in self._posts.values() if p.scraped_at >= cutoff]
        posts.sort(key=lambda p: p.scraped_at, reverse=True)
        return posts[:limit]

    def get_stats(self) -> HateSpeechStats:
        now = datetime.now(UTC)
        cutoff_24h = now - timedelta(hours=24)
        cutoff_1h = now - timedelta(hours=1)

        all_posts = list(self._posts.values())
        flagged = [p for p in all_posts if p.is_flagged]

        # Category counts
        by_cat: dict[str, int] = {}
        for p in flagged:
            by_cat[p.category] = by_cat.get(p.category, 0) + 1

        # Language counts
        by_lang: dict[str, int] = {}
        for p in flagged:
            by_lang[p.language] = by_lang.get(p.language, 0) + 1

        # Keyword frequency
        kw_freq: dict[str, int] = {}
        for p in flagged:
            for kw in p.keyword_matches:
                kw_freq[kw] = kw_freq.get(kw, 0) + 1
        top_kw = sorted(kw_freq.items(), key=lambda x: x[1], reverse=True)[:10]

        # Top flagged accounts
        acct_freq: dict[str, int] = {}
        for p in flagged:
            if p.author_handle:
                acct_freq[p.author_handle] = acct_freq.get(p.author_handle, 0) + 1
        top_accounts = [h for h, _ in sorted(acct_freq.items(), key=lambda x: x[1], reverse=True)[:5]]

        last_scan: datetime | None = None
        if all_posts:
            last_scan = max(p.scraped_at for p in all_posts)

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
        )

    def review_post(self, post_id: str, action: str) -> bool:
        """Mark a post as reviewed. action: 'confirmed' | 'dismissed'."""
        post = self._posts.get(post_id)
        if not post:
            return False
        post.reviewed = True
        post.review_action = action
        return True


social_monitor_service = SocialMonitorService()
