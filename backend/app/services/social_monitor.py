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
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.services.hate_speech_detector import HateSpeechResult, hate_speech_detector
from app.services.x_scraper import ScrapedPost, TrendTopic, x_scraper_service

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


# ── Demo posts ─────────────────────────────────────────────────────────────────
# (handle, lang, content, kw_matches, category, score, hashtags, likes, rts, replies, trend)

_DEMO_POSTS = [
    ("user_beiRUT01", "ar",
     "الشيعة والسنة لازم يرحلوا من لبنان، هالبلد ما رح يتعدل بوجودهم #لبنان",
     ["شيعة", "سنة"], "sectarian", 82, ["لبنان"], 120, 45, 30, "لبنان"),
    ("anti_leb_2024", "ar",
     "الروافض كفار ومين يتعاون معهم خاين #حزب_الله",
     ["روافض", "حزب الشيطان"], "sectarian", 91, ["حزب_الله"], 55, 22, 18, "حزب_الله"),
    ("free_leb_99", "en",
     "The Shia militias are destroying Lebanon, they should be eliminated permanently.",
     ["shia", "militia"], "sectarian", 78, [], 88, 33, 27, "Lebanon"),
    ("Leb_patriot77", "en",
     "Sunni extremists funded by Gulf states are the real problem in Lebanon. #Lebanon",
     ["sunni"], "sectarian", 65, ["Lebanon"], 210, 77, 54, "Lebanon"),
    ("anon_troll", "en",
     "Shia politicians are destroying Lebanon from within. When will people wake up?",
     ["shia"], "sectarian", 67, [], 445, 178, 112, "Lebanon"),
    ("news_comment_ar", "ar",
     "درزية ومسيحيين ومسلمين، كلهم بدهم يدمروا لبنان بطريقتهم",
     ["درزي", "ماروني"], "sectarian", 74, [], 92, 34, 27, "لبنان"),
    ("lebanese_first", "ar",
     "السوريين النازحين يسرقون فرص اللبنانيين، طردوهم كلهم #سوريا_ارحلوا",
     ["نازح", "سوري"], "anti_refugee", 88, ["سوريا_ارحلوا"], 340, 112, 89, "اللاجئون_السوريون"),
    ("Rima_LB", "fr",
     "Les réfugiés syriens volent nos emplois et nos ressources. Ils doivent partir.",
     ["réfugié", "syrien"], "anti_refugee", 73, [], 67, 28, 19, "لبنان"),
    ("leb_nat2023", "en",
     "Palestinian camp residents are a threat to Lebanese sovereignty. #BeirutFirst",
     ["palestinian", "camp"], "anti_refugee", 69, ["BeirutFirst"], 155, 61, 43, "Beirut"),
    ("voice_of_leb", "ar",
     "الفلسطينيين في المخيمات مسلحين ويهددون الأمن اللبناني. حل المخيمات فوراً!",
     ["فلسطيني", "مخيم"], "anti_refugee", 84, [], 289, 94, 67, "بيروت"),
    ("freedom_leb", "ar",
     "يستحق الموت كل من يتعاون مع الاحتلال الإيراني في لبنان #مقاومة",
     ["يستحق الموت"], "political_incite", 95, ["مقاومة"], 178, 89, 55, "حزب_الله"),
    ("resistance_2024", "en",
     "Political leaders who support Hezbollah should be executed without trial. #Lebanon",
     ["execute"], "political_incite", 90, ["Lebanon"], 234, 102, 77, "Lebanon"),
    ("anon_account_x", "ar",
     "يجب تصفية كل من يتعاون مع إسرائيل في لبنان، لا عفو ولا مسامحة.",
     ["يجب تصفيته", "اغتيال"], "political_incite", 93, [], 456, 201, 143, "اسرائيل_لبنان"),
    ("leb_trad_man", "ar",
     "المرأة اللبنانية التي تشارك في السياسة هي قحبة وما تستاهل احترام #نساء",
     ["قحبة"], "misogynistic", 87, [], 67, 18, 24, "لبنان"),
    ("news_follower", "ar",
     "الوضع في لبنان يزداد سوءاً بسبب الفساد السياسي والطائفية المتجذرة",
     [], "clean", 18, ["لبنان"], 89, 34, 22, "لبنان"),
    ("lebanon_watch", "en",
     "Sectarian divisions in Lebanon make governance almost impossible. Reform is needed.",
     [], "clean", 12, ["Lebanon"], 156, 58, 41, "Lebanon"),
]


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
        self._rng = random.Random(42)
        self._last_trend_map: dict[str, TrendTopic] = {}  # trend.name → TrendTopic

    # ── Demo data ─────────────────────────────────────────────────────────────

    async def seed_demo_posts(self) -> int:
        """Seed realistic demo posts when real scraping returns 0."""
        now = datetime.now(UTC)
        added = 0
        for i, row in enumerate(_DEMO_POSTS):
            handle, lang, content, kw_matches, category, score, hashtags, likes, rts, replies, trend = row
            post_id = f"x:demo_{i:04d}"
            if post_id in self._posts:
                continue
            hours_ago = self._rng.uniform(0.5, 23.0)
            posted_at = now - timedelta(hours=hours_ago)
            eng_total = likes + rts + replies
            velocity = min(100.0, eng_total / max(0.1, hours_ago))
            trend_rank = i + 1
            post = SocialPost(
                id=post_id,
                platform="x",
                author_handle=handle,
                author_id=f"uid_{handle}",
                author_age_days=self._rng.randint(15, 1800),
                content=content,
                language=lang,
                hate_score=float(score),
                category=category,
                is_flagged=score >= 51,
                keyword_matches=kw_matches,
                model_confidence=round(score / 100 * self._rng.uniform(0.85, 0.99), 3),
                like_count=likes,
                retweet_count=rts,
                reply_count=replies,
                quote_count=self._rng.randint(0, 20),
                engagement_total=eng_total,
                posted_at=posted_at,
                scraped_at=now,
                source_url=f"https://x.com/{handle}/status/{10000000000 + i}",
                hashtags=hashtags,
                matched_trend=trend,
                engagement_velocity=velocity,
                priority_score=_compute_priority(float(score), velocity, trend_rank, None),
            )
            self._posts[post_id] = post
            added += 1
        logger.info("Seeded %d demo hate speech posts", added)
        return added

    # ── Pipeline ──────────────────────────────────────────────────────────────

    async def run_scan(self, include_replies: bool = True) -> dict[str, int]:
        """Run a full trend-discovery → scrape → detect → score cycle.

        Returns summary counts: {scraped, analyzed, flagged}.
        """
        logger.info("Social monitor: starting trend-first scan")
        scraped: list[ScrapedPost] = []
        trends: list[TrendTopic] = []

        # ── Stage 1 + 2: Discover trends → scrape tweets ──
        try:
            trends = await x_scraper_service.discover_trends(max_trends=15)
            # Update local trend map for priority scoring
            self._last_trend_map = {t.name.lower(): t for t in trends}

            trending_posts = await x_scraper_service.scrape_for_trends(
                trends, tweets_per_trend=20
            )
            if trending_posts:
                logger.info("Trend-first scrape: %d posts from %d trends", len(trending_posts), len(trends))
                scraped.extend(trending_posts)
        except Exception as exc:
            logger.warning("Trend-first scrape failed: %s", exc)

        # ── Fallback: query-based scraping ──
        if not scraped:
            try:
                query_posts = await x_scraper_service.scrape_queries()
                scraped.extend(query_posts)
            except Exception as exc:
                logger.warning("Query scrape fallback failed: %s", exc)

        # ── Demo data when no real scraping succeeded ──
        if not scraped:
            logger.info("No posts scraped — loading demo data for UI testing")
            demo_added = await self.seed_demo_posts()
            return {"scraped": demo_added, "analyzed": demo_added, "flagged": sum(
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

        # Prune old entries (keep last 72h)
        cutoff = datetime.now(UTC) - timedelta(hours=72)
        self._posts = {k: v for k, v in self._posts.items() if v.scraped_at >= cutoff}

        logger.info(
            "Social monitor scan: scraped=%d analyzed=%d flagged=%d trends=%d",
            len(scraped), analyzed, flagged, len(trends),
        )
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

    def review_post(self, post_id: str, action: str) -> bool:
        """Mark a post as reviewed. action: 'confirmed' | 'dismissed'."""
        post = self._posts.get(post_id)
        if not post:
            return False
        post.reviewed = True
        post.review_action = action
        return True


social_monitor_service = SocialMonitorService()
