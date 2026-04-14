"""Social Media Hate Speech Monitor Service.

Orchestrates the full pipeline:
  1. Scrape X posts via x_scraper_service
  2. Run hate_speech_detector on each post
  3. Store results in memory (+ PostgreSQL when STORAGE_MODE=postgres)
  4. Expose aggregated stats and flagged post feed

In-memory store mirrors the pattern used by local_store.py so the
feature works in both local and postgres modes.

When no X accounts are configured and the store is empty, a set of
realistic demo posts is seeded automatically so the UI is always
functional (demo mode).
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
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


# ── Demo post definitions ─────────────────────────────────────────────────────
# (handle, lang, content, keyword_matches, category, score, hashtags, likes, rts, replies)

_DEMO_POSTS = [
    # sectarian — Arabic
    ("user_beiRUT01",   "ar",
     "الشيعة والسنة لازم يرحلوا من لبنان، هالبلد ما رح يتعدل بوجودهم #لبنان",
     ["شيعة", "سنة"], "sectarian", 82, ["لبنان"], 120, 45, 30),
    ("anti_leb_2024",   "ar",
     "الروافض كفار ومين يتعاون معهم خاين #حزب_الله",
     ["روافض", "حزب الشيطان"], "sectarian", 91, ["حزب_الله"], 55, 22, 18),
    ("free_leb_99",     "en",
     "The Shia militias are destroying Lebanon, they should be eliminated permanently.",
     ["shia", "militia"], "sectarian", 78, [], 88, 33, 27),
    ("Leb_patriot77",   "en",
     "Sunni extremists funded by Gulf states are the real problem in Lebanon. #Lebanon",
     ["sunni"], "sectarian", 65, ["Lebanon"], 210, 77, 54),
    ("anon_troll",      "en",
     "Shia politicians are destroying Lebanon from within. When will people wake up?",
     ["shia"], "sectarian", 67, [], 445, 178, 112),
    ("news_comment_ar", "ar",
     "درزية ومسيحيين ومسلمين، كلهم بدهم يدمروا لبنان بطريقتهم",
     ["درزي", "ماروني"], "sectarian", 74, [], 92, 34, 27),
    ("casual_user_leb", "ar",
     "الميليشيات الطائفية في لبنان هي السبب الرئيسي لكل الأزمات",
     ["ميليشيا", "شيعي"], "sectarian", 55, ["لبنان"], 134, 52, 38),
    ("leb_politics",    "en",
     "The militia groups backed by Iran have turned Lebanon into a proxy battleground.",
     ["militia"], "sectarian", 58, [], 220, 87, 64),
    # anti_refugee — Arabic / French / English
    ("lebanese_first",  "ar",
     "السوريين النازحين يسرقون فرص اللبنانيين، طردوهم كلهم #سوريا_ارحلوا",
     ["نازح", "سوري", "النازحين"], "anti_refugee", 88, ["سوريا_ارحلوا"], 340, 112, 89),
    ("Rima_LB",         "fr",
     "Les réfugiés syriens volent nos emplois et nos ressources. Ils doivent partir.",
     ["réfugié", "syrien", "déplacé"], "anti_refugee", 73, [], 67, 28, 19),
    ("leb_nat2023",     "en",
     "Palestinian camp residents are a threat to Lebanese sovereignty. #BeirutFirst",
     ["palestinian", "camp"], "anti_refugee", 69, ["BeirutFirst"], 155, 61, 43),
    ("voice_of_leb",    "ar",
     "الفلسطينيين في المخيمات مسلحين ويهددون الأمن اللبناني. حل المخيمات فوراً!",
     ["فلسطيني", "مخيم"], "anti_refugee", 84, ["مخيم"], 289, 94, 67),
    ("concerned_leb",   "ar",
     "لو ما كانوا النازحين بلبنان كانت الأوضاع الاقتصادية أحسن بكتير",
     ["نازح"], "anti_refugee", 53, [], 98, 37, 25),
    ("daily_rant_leb",  "en",
     "Refugee crisis is bleeding Lebanon dry. The government does nothing.",
     ["refugee", "displaced"], "anti_refugee", 61, [], 310, 124, 88),
    # political_incite
    ("freedom_leb",     "ar",
     "يستحق الموت كل من يتعاون مع الاحتلال الإيراني في لبنان #مقاومة",
     ["يستحق الموت"], "political_incite", 95, ["مقاومة"], 178, 89, 55),
    ("resistance_2024", "en",
     "Political leaders who support Hezbollah should be executed without trial. #Lebanon",
     ["execute"], "political_incite", 90, ["Lebanon"], 234, 102, 77),
    ("lebanese_anger",  "fr",
     "Il faut éliminer tous les politiciens corrompus de ce pays. #LibanLibre",
     ["éliminer"], "political_incite", 76, ["LibanLibre"], 98, 41, 33),
    ("anon_account_x",  "ar",
     "يجب تصفية كل من يتعاون مع إسرائيل في لبنان، لا عفو ولا مسامحة.",
     ["يجب تصفيته", "اغتيال"], "political_incite", 93, [], 456, 201, 143),
    ("fr_user_leb",     "fr",
     "Les milices chiites ont volé l'état libanais. Il faut les neutraliser.",
     ["chiite"], "political_incite", 80, [], 134, 55, 39),
    ("leb_voice_2025",  "ar",
     "هالنواب اللي بالبرلمان يستاهلوا يتعاقبوا بقسوة على كل ما عملوه بالبلد",
     [], "political_incite", 42, ["لبنان"], 187, 73, 51),
    # misogynistic
    ("leb_trad_man",    "ar",
     "المرأة اللبنانية التي تشارك في السياسة هي قحبة وما تستاهل احترام #نساء",
     ["قحبة", "ناقصة عقل"], "misogynistic", 87, ["نساء"], 67, 18, 24),
    ("anon_user_88",    "en",
     "Women in Lebanese politics are just there to look good. Go back to kitchen.",
     ["go back to kitchen", "woman should"], "misogynistic", 72, [], 43, 15, 19),
    # clean (lower score — below flag threshold)
    ("news_follower",   "ar",
     "الوضع في لبنان يزداد سوءاً بسبب الفساد السياسي والطائفية المتجذرة",
     [], "clean", 18, ["لبنان"], 89, 34, 22),
    ("lebanon_watch",   "en",
     "Sectarian divisions in Lebanon make governance almost impossible. Reform is needed.",
     [], "clean", 12, ["Lebanon"], 156, 58, 41),
    ("leb_observer",    "fr",
     "Le sectarisme au Liban est un frein majeur au développement économique.",
     [], "clean", 8, [], 72, 27, 18),
]


class SocialMonitorService:
    """In-memory store + pipeline orchestrator for hate speech monitoring."""

    def __init__(self) -> None:
        self._posts: dict[str, SocialPost] = {}   # id → SocialPost
        self._is_running = False
        self._scan_interval_seconds = 1800         # 30 minutes
        self._rng = random.Random(42)

    # ── Demo data (used when X scraping is unavailable) ──────────────────────

    async def seed_demo_posts(self) -> int:
        """Populate the store with realistic demo posts for UI testing.
        Called automatically when real scraping returns 0 results.
        """
        now = datetime.now(UTC)
        added = 0
        for i, row in enumerate(_DEMO_POSTS):
            handle, lang, content, kw_matches, category, score, hashtags, likes, rts, replies = row
            post_id = f"x:demo_{i:04d}"
            if post_id in self._posts:
                continue
            hours_ago = self._rng.uniform(0.5, 23.0)
            posted_at = now - timedelta(hours=hours_ago)
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
                engagement_total=likes + rts + replies,
                posted_at=posted_at,
                scraped_at=now,
                source_url=f"https://twitter.com/{handle}/status/{10000000000 + i}",
                hashtags=hashtags,
            )
            self._posts[post_id] = post
            added += 1

        logger.info("Seeded %d demo hate speech posts", added)
        return added

    # ── Pipeline ──────────────────────────────────────────────────────────────

    async def run_scan(self, include_replies: bool = True) -> dict[str, int]:
        """Run a full scrape + detection cycle. Returns summary counts.
        Falls back to demo data when no real scraping succeeds.
        """
        logger.info("Social monitor: starting X scan")
        scraped: list[ScrapedPost] = []

        try:
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

        # If X scraping produced nothing, seed demo data (demo/dev mode)
        if not scraped:
            logger.info("No posts scraped from X — loading demo data for UI testing")
            demo_added = await self.seed_demo_posts()
            return {"scraped": demo_added, "analyzed": demo_added, "flagged": sum(
                1 for p in self._posts.values() if p.is_flagged
            )}

        analyzed = 0
        flagged = 0

        for raw in scraped:
            post_id = f"x:{raw.post_id}"
            if post_id in self._posts:
                continue

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
        self._posts = {k: v for k, v in self._posts.items() if v.scraped_at >= cutoff}

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

        by_cat: dict[str, int] = {}
        for p in flagged:
            by_cat[p.category] = by_cat.get(p.category, 0) + 1

        by_lang: dict[str, int] = {}
        for p in flagged:
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
