"""X (Twitter) Scraper Service — Lebanon Trend-First Architecture.

Pipeline stages:
  1. Trend Discovery  — fetch current Lebanon trends from X API (or curated fallback)
  2. Tweet Collection — scrape top-engagement tweets for each trend/hashtag
  3. Metadata enrichment — each ScrapedPost carries matched_trend + engagement_velocity

This replaces the old account-centric model (12 fixed influencer accounts).
The system now continuously discovers trending Lebanese discussions and collects
the most-interacted tweets around those trends for hate speech analysis.

Public API (XScraperService):
  discover_trends(max_trends)          → list[TrendTopic]
  scrape_for_trends(trends, per_trend) → list[ScrapedPost]   (main entry point)
  scrape_trending(max_hashtags, ...)   → list[ScrapedPost]   (compat wrapper)
  scrape_queries()                     → list[ScrapedPost]   (keyword fallback)
  scrape_media_timelines()             → list[ScrapedPost]   (account fallback)
  fetch_tweet_replies(tweet_id, limit) → list[ScrapedPost]
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)

# ── Lebanon WOEIDs ─────────────────────────────────────────────────────────────
LEBANON_WOEID = 23424873   # Lebanon country
BEIRUT_WOEID  = 2316588    # Beirut city

# ── Minimum engagement to keep a tweet ────────────────────────────────────────
MIN_ENGAGEMENT = 3

# ── Curated Lebanese hashtag pool — tiered by expected relevance ──────────────
# These are used as fallback when the X trends API is unavailable.
# Tier-1 (always monitored), Tier-2 (rotated), Tier-3 (supplementary)
CURATED_LB_HASHTAGS_TIER1 = [
    "لبنان",
    "بيروت",
    "Lebanon",
    "Beirut",
    "جنوب_لبنان",
    "الجنوب_اللبناني",
    "حزب_الله",
    "الجيش_اللبناني",
]
CURATED_LB_HASHTAGS_TIER2 = [
    "اللاجئون_السوريون",
    "النازحين_السوريين",
    "طائفية_لبنان",
    "الحكومة_اللبنانية",
    "اسرائيل_لبنان",
    "ايران_لبنان",
    "LebanonWar",
    "SyrianRefugees",
]
CURATED_LB_HASHTAGS_TIER3 = [
    "المقاومة",
    "الانتخابات_اللبنانية",
    "اقتصاد_لبنان",
    "كهرباء_لبنان",
    "ازمة_لبنان",
    "لبنان_ينتفض",
]

ALL_CURATED_HASHTAGS = (
    CURATED_LB_HASHTAGS_TIER1
    + CURATED_LB_HASHTAGS_TIER2
    + CURATED_LB_HASHTAGS_TIER3
)

# ── Lebanese influencer accounts (fallback only when search is blocked) ────────
# Verified working as of April 2026. Add/remove handles here as accounts change.
# Prefer high-frequency posters (news channels > politicians > activists).
LEBANESE_INFLUENCER_ACCOUNTS = [
    # ── TV / broadcast ──
    "LBCI_News",        # LBCI TV — multiple posts per hour
    "LBC_Group",        # LBC TV news feed
    "AlMayadeen_Eng",   # Al Mayadeen (English)
    "AlJadeedNews",     # Al Jadeed TV
    # ── Print / digital newspapers ──
    "Annahar",          # An-Nahar — major Arabic daily
    "AlJumhuriya",      # Al Jumhuriya newspaper
    "LOrientLeJour",    # L'Orient Le Jour (French/English)
    "DailyStarLeb",     # The Daily Star Lebanon
    "NaharNet",         # Naharnet English wire
    "The961",           # The961 — popular English news site
    # ── Wire services active on Lebanon ──
    "Reuters_Lebanon",  # Reuters Lebanon bureau
    "AFParabic",        # AFP Arabic breaking news
    # ── Politicians / key voices ──
    "Gebran_Bassil",    # FPM leader
    "saadhariri",       # Former PM Hariri
    # ── Civil society / monitoring ──
    "LebanonUprising",  # Civil uprising accounts
]

# ── Seed search queries (keyword fallback) ────────────────────────────────────
SEED_QUERIES = [
    "لبنان طائفية -filter:links",
    "حزب الله مسيحيين OR سنة OR درزية",
    "اللاجئين السوريين لبنان ارحلوا OR اخرجوا",
    "خطاب الكراهية لبنان",
    "النازحون السوريون لبنان مشكلة",
]

# ── Public hate speech queries — Arabic only, broad discovery, no account required
# Used by scrape_public_keywords() via XGuestScraper (guest token, no auth).
# Searches ALL public X posts — not restricted to specific accounts.
# Arabic-only: covers sectarian hate, anti-refugee, political incitement in Lebanon.
PUBLIC_HATE_SPEECH_QUERIES: list[str] = [
    # Sectarian hate
    "لبنان طائفية",
    "طائفة لبنان كراهية",
    "حزب الله مسيحيين",
    "لبنان شيعة سنة درزية",
    "تمييز طائفي لبنان",
    "طائفية لبنان 2025",
    # Anti-refugee
    "اللاجئين السوريين لبنان ارحلوا",
    "السوريين لبنان اخرجوا",
    "النازحون لبنان جريمة",
    "سوريين لبنان مشكلة",
    "اللاجئون السوريون يغادرون لبنان",
    # Political incitement
    "حزب الله ارهاب",
    "المقاومة لبنان جرائم",
    "لبنان تفجير ارهاب حزب",
    "الميليشيات لبنان",
    # General hate speech
    "خطاب الكراهية لبنان",
    "لبنان تمييز",
    "كراهية لبنان طائفة",
    # Hashtag-targeted (Arabic)
    "#طائفية_لبنان",
    "#اللاجئون_في_لبنان",
    "#لبنان طائفية",
    "#حزب_الله",
    "#اللاجئون_السوريون",
]

# ── X Bearer token (public, embedded in the official X web app) ───────────────
_X_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class TrendTopic:
    """A single Lebanon-trending topic/hashtag."""
    name: str                     # e.g. "لبنان" or "LebanonWar"
    display_name: str             # with # prefix: "#لبنان"
    tweet_volume: int | None      # estimated tweet volume from X trends API
    trend_rank: int               # 1 = most trending
    source: str                   # "x_api" | "curated" | "fallback"

    @property
    def rank_score(self) -> float:
        """0–100 score based on trend rank (rank 1 = 100, rank 10 = 10)."""
        return max(0.0, 100.0 - (self.trend_rank - 1) * 10.0)


@dataclass
class ScrapedPost:
    """A raw tweet from X before hate speech analysis."""
    post_id: str
    platform: str = "x"
    author_id: str = ""
    author_handle: str = ""
    author_created_at: datetime | None = None
    content: str = ""
    lang: str = ""
    like_count: int = 0
    retweet_count: int = 0
    reply_count: int = 0
    quote_count: int = 0
    posted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_url: str = ""
    in_reply_to_id: str | None = None
    hashtags: list[str] = field(default_factory=list)
    # Trend-first metadata
    matched_trend: str = ""       # which TrendTopic.name produced this post
    engagement_velocity: float = 0.0  # engagement per hour since posted

    @property
    def account_age_days(self) -> int | None:
        if self.author_created_at is None:
            return None
        return (datetime.now(UTC) - self.author_created_at).days

    @property
    def engagement_total(self) -> int:
        return self.like_count + self.retweet_count + self.reply_count + self.quote_count

    def compute_engagement_velocity(self) -> float:
        """Calculate engagement per hour, capped at 1000 (normalized to 0–100 scale)."""
        now = datetime.now(UTC)
        hours = max(0.1, (now - self.posted_at).total_seconds() / 3600)
        raw_velocity = self.engagement_total / hours
        # Normalize: 100 eng/hour → score 100 (log-scale friendly cap)
        self.engagement_velocity = min(100.0, raw_velocity)
        return self.engagement_velocity


# ── X Guest Scraper (no account — limited fallback) ────────────────────────────

_GUEST_TOKEN_URL = "https://api.twitter.com/1.1/guest/activate.json"
_SEARCH_URL      = "https://twitter.com/i/api/2/search/adaptive.json"


class XGuestScraper:
    """Scrapes X search results using the guest token endpoint (no account needed)."""

    def __init__(self) -> None:
        self._guest_token: str | None = None
        self._token_fetched_at: datetime | None = None

    async def _get_guest_token(self, client: httpx.AsyncClient) -> str:
        if (
            self._guest_token
            and self._token_fetched_at
            and datetime.now(UTC) - self._token_fetched_at < timedelta(hours=2)
        ):
            return self._guest_token
        try:
            resp = await client.post(
                _GUEST_TOKEN_URL,
                headers={
                    "Authorization": f"Bearer {_X_BEARER}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=10,
            )
            resp.raise_for_status()
            self._guest_token = resp.json()["guest_token"]
            self._token_fetched_at = datetime.now(UTC)
            return self._guest_token  # type: ignore[return-value]
        except Exception as exc:
            logger.warning("Failed to get X guest token: %s", exc)
            raise

    def _parse_tweet(self, tweet_data: dict) -> ScrapedPost | None:
        try:
            legacy = tweet_data.get("legacy", {})
            user = tweet_data.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {})
            post_id = legacy.get("id_str", "")
            content = legacy.get("full_text", "").strip()
            if not post_id or not content:
                return None
            clean_content = re.sub(r"http\S+", "", content).strip()
            author_handle = user.get("screen_name", "")
            author_id = user.get("id_str", "")
            author_created_at: datetime | None = None
            if user.get("created_at"):
                try:
                    author_created_at = datetime.strptime(
                        user["created_at"], "%a %b %d %H:%M:%S +0000 %Y"
                    ).replace(tzinfo=UTC)
                except ValueError:
                    pass
            posted_at = datetime.now(UTC)
            if legacy.get("created_at"):
                try:
                    posted_at = datetime.strptime(
                        legacy["created_at"], "%a %b %d %H:%M:%S +0000 %Y"
                    ).replace(tzinfo=UTC)
                except ValueError:
                    pass
            hashtags = [ht.get("text", "").lower() for ht in legacy.get("entities", {}).get("hashtags", [])]
            return ScrapedPost(
                post_id=post_id,
                author_id=author_id,
                author_handle=author_handle,
                author_created_at=author_created_at,
                content=clean_content or content,
                lang=legacy.get("lang", ""),
                like_count=int(legacy.get("favorite_count", 0)),
                retweet_count=int(legacy.get("retweet_count", 0)),
                reply_count=int(legacy.get("reply_count", 0)),
                quote_count=int(legacy.get("quote_count", 0)),
                posted_at=posted_at,
                source_url=f"https://twitter.com/{author_handle}/status/{post_id}",
                in_reply_to_id=legacy.get("in_reply_to_status_id_str"),
                hashtags=hashtags,
            )
        except Exception as exc:
            logger.debug("Could not parse tweet: %s", exc)
            return None

    async def search(self, query: str, limit: int = 50) -> list[ScrapedPost]:
        posts: list[ScrapedPost] = []
        try:
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; CrisisShield/1.0)"},
            ) as client:
                token = await self._get_guest_token(client)
                params = {
                    "q": query,
                    "count": min(limit, 100),
                    "tweet_mode": "extended",
                    "result_type": "recent",
                    "lang": "",
                    "tweet_search_mode": "live",
                }
                resp = await client.get(
                    _SEARCH_URL,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {_X_BEARER}",
                        "x-guest-token": token,
                        "x-twitter-active-user": "yes",
                        "x-twitter-client-language": "en",
                    },
                )
                if resp.status_code != 200:
                    logger.warning("X search returned %d for query: %s", resp.status_code, query)
                    return []
                data = resp.json()
                tweet_dict = data.get("globalObjects", {}).get("tweets", {})
                user_dict = data.get("globalObjects", {}).get("users", {})
                for tweet_id, tweet in tweet_dict.items():
                    if len(posts) >= limit:
                        break
                    user_id = tweet.get("user_id_str", "")
                    user = user_dict.get(user_id, {})
                    post = ScrapedPost(
                        post_id=tweet_id,
                        author_id=user_id,
                        author_handle=user.get("screen_name", ""),
                        content=re.sub(r"http\S+", "", tweet.get("full_text", "")).strip(),
                        lang=tweet.get("lang", ""),
                        like_count=int(tweet.get("favorite_count", 0)),
                        retweet_count=int(tweet.get("retweet_count", 0)),
                        reply_count=int(tweet.get("reply_count", 0)),
                        quote_count=int(tweet.get("quote_count", 0)),
                        source_url=f"https://twitter.com/{user.get('screen_name','')}/status/{tweet_id}",
                        hashtags=[ht.get("text", "").lower() for ht in tweet.get("entities", {}).get("hashtags", [])],
                    )
                    posted_raw = tweet.get("created_at", "")
                    if posted_raw:
                        try:
                            post.posted_at = datetime.strptime(
                                posted_raw, "%a %b %d %H:%M:%S +0000 %Y"
                            ).replace(tzinfo=UTC)
                        except ValueError:
                            pass
                    if post.content:
                        posts.append(post)
        except Exception as exc:
            logger.warning("X guest scrape failed for '%s': %s", query, exc)
        return posts


# ── Core scraper (twscrape + direct HTTP) ─────────────────────────────────────

class TwscrapeScraper:
    """Authenticated X scraper.

    Uses twscrape for account management + direct httpx GraphQL calls
    (bypassing twscrape's queue client to avoid account-locking).

    Key methods:
      discover_trends()       — fetch Lebanon trending topics
      search_hashtag_top()    — SearchTimeline GraphQL for a hashtag
      fetch_user_timeline()   — direct UserTweets GraphQL (account fallback)
      fetch_tweet_replies()   — TweetDetail GraphQL for reply threads
    """

    def __init__(self) -> None:
        self._api: object | None = None
        self._loaded = False
        self._user_id_cache: dict[str, int] = {}

    def _load(self) -> bool:
        if self._loaded:
            return self._api is not None
        try:
            from twscrape import API  # type: ignore[import]
            db_candidates = [
                "/app/twscrape_accounts.db",
                os.path.join(os.path.dirname(__file__), "../../../twscrape_accounts.db"),
                os.path.expanduser("~/.local/share/twscrape/accounts.db"),
            ]
            db_path = next((p for p in db_candidates if os.path.exists(p)), None)
            self._api = API(db_path) if db_path else API()
            self._loaded = True
            logger.info("twscrape API loaded (db=%s)", db_path or "default")
            return True
        except ImportError:
            logger.info("twscrape not installed — authenticated scraping disabled")
            self._api = None
            self._loaded = True
            return False

    def _get_db_path(self) -> str | None:
        candidates = [
            "/app/twscrape_accounts.db",
            os.path.join(os.path.dirname(__file__), "../../../twscrape_accounts.db"),
            os.path.expanduser("~/.local/share/twscrape/accounts.db"),
        ]
        return next((p for p in candidates if os.path.exists(p)), None)

    def _read_active_account(self) -> tuple[str, dict] | None:
        """Read the first active account cookies from the DB. Returns (username, cookies)."""
        import json as _json, sqlite3 as _sqlite3
        db_path = self._get_db_path()
        if not db_path:
            return None
        try:
            conn = _sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT username, cookies FROM accounts WHERE active=1 LIMIT 1")
            row = cur.fetchone()
            conn.close()
            if not row or not row[1]:
                return None
            cookies: dict = _json.loads(row[1])
            if not cookies.get("auth_token"):
                return None
            return row[0], cookies
        except Exception as exc:
            logger.debug("_read_active_account failed: %s", exc)
            return None

    def _make_auth_headers(self, cookies: dict, extra: dict | None = None) -> dict:
        h = {
            "Authorization": f"Bearer {_X_BEARER}",
            "x-csrf-token": cookies.get("ct0", ""),
            "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://x.com/",
            "Origin": "https://x.com",
        }
        if extra:
            h.update(extra)
        return h

    async def _get_xclid_gen(self, username: str) -> object | None:
        try:
            from twscrape.xclid import XClIdGen  # type: ignore[import]
            from twscrape.queue_client import XClIdGenStore  # type: ignore[import]
            if username not in XClIdGenStore.items:
                try:
                    gen = await XClIdGen.create()
                    XClIdGenStore.items[username] = gen
                except Exception as exc:
                    logger.debug("XClIdGen.create() failed: %s", exc)
                    XClIdGenStore.items[username] = None  # type: ignore[assignment]
            return XClIdGenStore.items.get(username)
        except ImportError:
            return None

    def _parse_tweet_entry(self, entry: dict, now: datetime) -> ScrapedPost | None:
        """Parse a GraphQL timeline entry into a ScrapedPost."""
        try:
            tweet_data = (
                entry.get("content", {})
                .get("itemContent", {})
                .get("tweet_results", {})
                .get("result", {})
            )
            if not tweet_data or tweet_data.get("__typename") != "Tweet":
                return None
            return self._parse_tweet_result(tweet_data, now)
        except Exception:
            return None

    def _parse_tweet_result(self, tweet_data: dict, now: datetime) -> ScrapedPost | None:
        """Parse a tweet_results.result dict into a ScrapedPost."""
        try:
            legacy = tweet_data.get("legacy", {})
            user_legacy = (
                tweet_data.get("core", {})
                .get("user_results", {})
                .get("result", {})
                .get("legacy", {})
            )
            content = re.sub(r"http\S+", "", legacy.get("full_text", "")).strip()
            if not content:
                return None
            post_id = legacy.get("id_str", "")
            if not post_id:
                return None
            posted_at = now
            if legacy.get("created_at"):
                try:
                    posted_at = datetime.strptime(
                        legacy["created_at"], "%a %b %d %H:%M:%S +0000 %Y"
                    ).replace(tzinfo=UTC)
                except ValueError:
                    pass
            author_created_at: datetime | None = None
            if user_legacy.get("created_at"):
                try:
                    author_created_at = datetime.strptime(
                        user_legacy["created_at"], "%a %b %d %H:%M:%S +0000 %Y"
                    ).replace(tzinfo=UTC)
                except ValueError:
                    pass
            handle = user_legacy.get("screen_name", "")
            return ScrapedPost(
                post_id=post_id,
                author_id=user_legacy.get("id_str", ""),
                author_handle=handle,
                author_created_at=author_created_at,
                content=content,
                lang=legacy.get("lang", ""),
                like_count=int(legacy.get("favorite_count", 0)),
                retweet_count=int(legacy.get("retweet_count", 0)),
                reply_count=int(legacy.get("reply_count", 0)),
                quote_count=int(legacy.get("quote_count", 0)),
                posted_at=posted_at,
                source_url=f"https://x.com/{handle}/status/{post_id}",
                in_reply_to_id=legacy.get("in_reply_to_status_id_str"),
                hashtags=[ht.get("text", "").lower() for ht in legacy.get("entities", {}).get("hashtags", [])],
            )
        except Exception as exc:
            logger.debug("_parse_tweet_result error: %s", exc)
            return None

    # ── Stage 1: Trend Discovery ──────────────────────────────────────────────

    async def discover_trends(self, woeid: int = LEBANON_WOEID) -> list[TrendTopic]:
        """Fetch current Lebanon trending topics.

        Strategy:
        1. X v1.1 trends/place.json API (authenticated with account cookies)
        2. X v1.1 trends/place.json API (Bearer-only, may work for some regions)
        3. Curated Lebanese hashtag pool (always succeeds)

        Returns a list of TrendTopic objects sorted by trend_rank.
        """
        # ── Strategy 1: Authenticated v1.1 trends API ──
        account = self._read_active_account()
        if account:
            username, cookies = account
            try:
                headers = {
                    "Authorization": f"Bearer {_X_BEARER}",
                    "x-csrf-token": cookies.get("ct0", ""),
                    "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
                    "x-twitter-auth-type": "OAuth2Session",
                    "x-twitter-active-user": "yes",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                }
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(
                        f"https://api.twitter.com/1.1/trends/place.json?id={woeid}",
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        trends_raw = resp.json()
                        if trends_raw and isinstance(trends_raw, list):
                            topics = self._parse_trends_response(trends_raw, source="x_api")
                            if topics:
                                logger.info(
                                    "Lebanon trends (authenticated): %s",
                                    [t.display_name for t in topics[:8]],
                                )
                                return topics
            except Exception as exc:
                logger.debug("Authenticated trends call failed: %s", exc)

        # ── Strategy 2: Bearer-only (limited regions) ──
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://api.twitter.com/1.1/trends/place.json?id={woeid}",
                    headers={"Authorization": f"Bearer {_X_BEARER}"},
                )
                if resp.status_code == 200:
                    trends_raw = resp.json()
                    if trends_raw and isinstance(trends_raw, list):
                        topics = self._parse_trends_response(trends_raw, source="x_api")
                        if topics:
                            logger.info(
                                "Lebanon trends (bearer-only): %s",
                                [t.display_name for t in topics[:8]],
                            )
                            return topics
        except Exception as exc:
            logger.debug("Bearer-only trends call failed: %s", exc)

        # ── Strategy 3: Curated pool (always available) ──
        logger.info("X trends API unavailable — using curated Lebanese hashtag pool")
        return self._curated_trend_topics()

    def _parse_trends_response(self, trends_raw: list, source: str) -> list[TrendTopic]:
        """Parse X v1.1 trends/place.json response into TrendTopic list."""
        topics: list[TrendTopic] = []
        raw_trends = trends_raw[0].get("trends", []) if trends_raw else []
        for i, t in enumerate(raw_trends, 1):
            name_raw: str = t.get("name", "")
            if not name_raw:
                continue
            # Filter to Lebanon-relevant trends
            name_clean = name_raw.lstrip("#")
            topics.append(TrendTopic(
                name=name_clean,
                display_name=f"#{name_clean}" if not name_raw.startswith("#") else name_raw,
                tweet_volume=t.get("tweet_volume"),
                trend_rank=i,
                source=source,
            ))
        return topics

    def _curated_trend_topics(self) -> list[TrendTopic]:
        """Build TrendTopic list from the curated hashtag pool."""
        topics: list[TrendTopic] = []
        all_tags = CURATED_LB_HASHTAGS_TIER1 + CURATED_LB_HASHTAGS_TIER2 + CURATED_LB_HASHTAGS_TIER3
        for i, tag in enumerate(all_tags, 1):
            topics.append(TrendTopic(
                name=tag.lstrip("#"),
                display_name=f"#{tag.lstrip('#')}",
                tweet_volume=None,
                trend_rank=i,
                source="curated",
            ))
        return topics

    # ── Stage 2: Tweet Collection per Trend ──────────────────────────────────

    async def search_hashtag_top(
        self,
        trend: TrendTopic,
        limit: int = 20,
    ) -> list[ScrapedPost]:
        """Search for top-engagement tweets for a given trend using SearchTimeline GraphQL.

        Uses product='Top' which returns most-interacted tweets (works better than
        'Latest' for non-phone-verified accounts in many cases).

        Each returned ScrapedPost has matched_trend set to trend.name.
        """
        if not self._load() or self._api is None:
            return []

        account = self._read_active_account()
        if not account:
            return []

        username, cookies = account

        try:
            from twscrape.api import OP_SearchTimeline, GQL_FEATURES  # type: ignore[import]
        except ImportError:
            return []

        gen = await self._get_xclid_gen(username)
        # NOTE: X routes /{hash}/SearchTimeline/SearchTimeline differently from
        # /{hash}/SearchTimeline — the former returns 200 for non-phone-verified
        # accounts whereas the latter returns 404. Keep the appended operation
        # name suffix to preserve this behaviour.
        st_path = f"/i/api/graphql/{OP_SearchTimeline}/SearchTimeline"

        headers = self._make_auth_headers(cookies, {
            "x-twitter-client-language": "ar",
        })
        if gen:
            headers["x-client-transaction-id"] = gen.calc("GET", st_path)  # type: ignore[attr-defined]

        # Build query: Arabic hashtag, prefer Top (most-interacted) results
        tag_name = trend.name.lstrip("#")
        query = f"#{tag_name} lang:ar"

        variables = {
            "rawQuery": query,
            "count": min(limit, 20),
            "querySource": "hashtag_click",
            "product": "Top",
        }

        try:
            import json as _json
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://x.com{st_path}",
                    params={
                        "variables": _json.dumps(variables, ensure_ascii=False),
                        "features": _json.dumps(GQL_FEATURES),
                    },
                    headers=headers,
                )

                if resp.status_code != 200:
                    logger.debug("SearchTimeline #%s: %d", tag_name, resp.status_code)
                    return []

                data = resp.json()
                instructions = (
                    data.get("data", {})
                    .get("search_by_raw_query", {})
                    .get("search_timeline", {})
                    .get("timeline", {})
                    .get("instructions", [])
                )

                posts: list[ScrapedPost] = []
                now = datetime.now(UTC)

                for instruction in instructions:
                    for entry in instruction.get("entries", []):
                        post = self._parse_tweet_entry(entry, now)
                        if post and post.content:
                            if post.engagement_total < MIN_ENGAGEMENT:
                                continue
                            post.matched_trend = trend.name
                            post.compute_engagement_velocity()
                            posts.append(post)
                        if len(posts) >= limit:
                            break

                logger.info("SearchTimeline #%s (rank %d) → %d posts", tag_name, trend.trend_rank, len(posts))
                return posts

        except Exception as exc:
            logger.debug("search_hashtag_top failed for #%s: %s", tag_name, exc)
            return []

    async def fetch_user_timeline(self, handle: str, limit: int = 30) -> list[ScrapedPost]:
        """Fetch a user's recent tweets via direct UserTweets GraphQL (bypasses queue client)."""
        if not self._load() or self._api is None:
            return []

        account = self._read_active_account()
        if not account:
            return []

        username, cookies = account
        gen = await self._get_xclid_gen(username)
        base_headers = self._make_auth_headers(cookies, {"x-twitter-client-language": "en"})

        try:
            import json as _json
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                # Step 1: resolve handle → user_id
                if handle in self._user_id_cache:
                    user_id = self._user_id_cache[handle]
                    screen_name = handle
                else:
                    from twscrape.api import OP_UserByScreenName  # type: ignore[import]
                    ub_path = f"/i/api/graphql/{OP_UserByScreenName}"
                    ub_headers = {**base_headers}
                    if gen:
                        ub_headers["x-client-transaction-id"] = gen.calc("GET", ub_path)  # type: ignore[attr-defined]
                    resp = await client.get(
                        f"https://x.com{ub_path}",
                        params={
                            "variables": _json.dumps({"screen_name": handle, "withSafetyModeUserFields": True}),
                            "features": _json.dumps({"hidden_profile_likes_enabled": True, "hidden_profile_subscriptions_enabled": True}),
                        },
                        headers=ub_headers,
                    )
                    if resp.status_code == 429:
                        logger.warning("UserByScreenName @%s: rate limited (429)", handle)
                        return []
                    if resp.status_code != 200:
                        logger.warning("UserByScreenName @%s: %d", handle, resp.status_code)
                        return []
                    result = resp.json().get("data", {}).get("user", {}).get("result", {})
                    user_id = result.get("rest_id") or result.get("legacy", {}).get("id_str")
                    screen_name = result.get("legacy", {}).get("screen_name", handle)
                    if not user_id:
                        return []
                    self._user_id_cache[handle] = user_id  # type: ignore[assignment]

                # Step 2: fetch tweets
                from twscrape.api import GQL_FEATURES, OP_UserTweets  # type: ignore[import]
                ut_path = f"/i/api/graphql/{OP_UserTweets}"
                ut_headers = {**base_headers}
                if gen:
                    ut_headers["x-client-transaction-id"] = gen.calc("GET", ut_path)  # type: ignore[attr-defined]

                variables = {
                    "userId": str(user_id),
                    "count": min(limit, 40),
                    "includePromotedContent": False,
                    "withQuickPromoteEligibilityTweetFields": True,
                    "withVoice": True,
                    "withV2Timeline": True,
                }
                resp2 = await client.get(
                    f"https://x.com{ut_path}",
                    params={
                        "variables": _json.dumps(variables),
                        "features": _json.dumps(GQL_FEATURES),
                    },
                    headers=ut_headers,
                )
                if resp2.status_code == 429:
                    logger.warning("UserTweets @%s: rate limited (429) — skipping account", handle)
                    return []
                if resp2.status_code != 200:
                    logger.warning("UserTweets @%s: %d — skipping", handle, resp2.status_code)
                    return []

                data = resp2.json()
                user_result = data.get("data", {}).get("user", {}).get("result", {})
                tl = user_result.get("timeline_v2") or user_result.get("timeline") or {}
                instructions = tl.get("timeline", {}).get("instructions", [])

                posts: list[ScrapedPost] = []
                now = datetime.now(UTC)
                for instruction in instructions:
                    for entry in instruction.get("entries", []):
                        post = self._parse_tweet_entry(entry, now)
                        if post and post.content:
                            post.compute_engagement_velocity()
                            posts.append(post)
                        if len(posts) >= limit:
                            break

                if posts:
                    logger.info("UserTweets @%s → %d tweets", handle, len(posts))
                else:
                    logger.debug("UserTweets @%s → 0 tweets (empty timeline or no entries)", handle)
                return posts

        except Exception as exc:
            logger.warning("fetch_user_timeline failed for @%s: %s", handle, exc)
            return []

    async def fetch_tweet_replies(self, tweet_id: str, limit: int = 20) -> list[ScrapedPost]:
        """Fetch replies to a tweet via TweetDetail GraphQL, sorted by most liked."""
        if not self._load() or self._api is None:
            return []

        account = self._read_active_account()
        if not account:
            return []

        username, cookies = account
        gen = await self._get_xclid_gen(username)

        try:
            from twscrape.api import OP_TweetDetail, GQL_FEATURES  # type: ignore[import]
        except ImportError:
            return []

        td_path = f"/i/api/graphql/{OP_TweetDetail}"
        headers = self._make_auth_headers(cookies, {
            "Referer": f"https://x.com/i/web/status/{tweet_id}",
        })
        if gen:
            headers["x-client-transaction-id"] = gen.calc("GET", td_path)  # type: ignore[attr-defined]

        variables = {
            "focalTweetId": tweet_id,
            "count": 40,
            "referrer": "tweet",
            "with_rux_injections": False,
            "rankingMode": "Relevance",
            "includePromotedContent": False,
            "withCommunity": True,
            "withQuickPromoteEligibilityTweetFields": True,
            "withBirdwatchNotes": True,
            "withVoice": True,
        }
        fieldtoggles = {
            "withArticleRichContentState": True,
            "withArticlePlainText": False,
            "withGrokAnalyze": False,
            "withDisallowedReplyControls": False,
        }

        try:
            import json as _json
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://x.com{td_path}",
                    params={
                        "variables": _json.dumps(variables),
                        "features": _json.dumps(GQL_FEATURES),
                        "fieldToggles": _json.dumps(fieldtoggles),
                    },
                    headers=headers,
                )
                if resp.status_code != 200:
                    logger.debug("TweetDetail %s: %d", tweet_id, resp.status_code)
                    return []

                data = resp.json()
                instructions = (
                    data.get("data", {})
                    .get("threaded_conversation_with_injections_v2", {})
                    .get("instructions", [])
                )

                replies: list[ScrapedPost] = []
                now = datetime.now(UTC)

                for instruction in instructions:
                    for entry in instruction.get("entries", []):
                        entry_id = entry.get("entryId", "")
                        if entry_id == f"tweet-{tweet_id}":
                            continue
                        # Two forms: direct entry or threaded module items
                        items_to_check = []
                        content = entry.get("content", {})
                        if content.get("entryType") == "TimelineTimelineModule":
                            for item in content.get("items", []):
                                items_to_check.append(item.get("item", {}))
                        else:
                            items_to_check.append(content)

                        for item_content in items_to_check:
                            try:
                                tweet_data = (
                                    item_content.get("itemContent", {})
                                    .get("tweet_results", {})
                                    .get("result", {})
                                )
                                if not tweet_data or tweet_data.get("__typename") != "Tweet":
                                    continue
                                legacy = tweet_data.get("legacy", {})
                                if legacy.get("in_reply_to_status_id_str") != tweet_id:
                                    continue
                                post = self._parse_tweet_result(tweet_data, now)
                                if post:
                                    post.in_reply_to_id = tweet_id
                                    replies.append(post)
                            except Exception:
                                continue

                replies.sort(key=lambda r: r.like_count, reverse=True)
                logger.info("TweetDetail %s → %d replies", tweet_id, len(replies))
                return replies[:limit]

        except Exception as exc:
            logger.warning("fetch_tweet_replies failed for %s: %s", tweet_id, exc)
            return []

    async def prewarm_xclid(self) -> bool:
        """Pre-generate XClientTxId so the first API call does not timeout."""
        if not self._load() or self._api is None:
            return False
        try:
            from twscrape.xclid import XClIdGen  # type: ignore[import]
            from twscrape.queue_client import XClIdGenStore  # type: ignore[import]
            gen = await XClIdGen.create()
            accounts = await self._api.pool.get_all()  # type: ignore[attr-defined]
            for acc in accounts:
                XClIdGenStore.items[acc.username] = gen
            logger.info("twscrape: XClientTxId pre-warmed for %d account(s)", len(accounts))
            return True
        except Exception as exc:
            logger.warning("twscrape: XClientTxId pre-warm failed: %s", exc)
            return False


# ── XScraperService — public API ──────────────────────────────────────────────

class XScraperService:
    """Unified X scraping service implementing the trend-first pipeline.

    Pipeline:
      discover_trends()         → list[TrendTopic]
      scrape_for_trends(trends) → list[ScrapedPost]   (posts tagged with matched_trend)
      scrape_trending()         → discover + scrape (convenience wrapper)
      scrape_queries()          → keyword search fallback
      scrape_media_timelines()  → account-based fallback
      fetch_tweet_replies()     → for reply modal in UI
    """

    def __init__(self) -> None:
        self._twscrape = TwscrapeScraper()
        self._guest = XGuestScraper()
        self._seen_ids: set[str] = set()
        # Cache the last discovered trends so social_monitor can access them
        self._last_trends: list[TrendTopic] = []

    def _dedup(self, posts: list[ScrapedPost]) -> list[ScrapedPost]:
        result = []
        for p in posts:
            if p.post_id not in self._seen_ids:
                self._seen_ids.add(p.post_id)
                result.append(p)
        if len(self._seen_ids) > 50_000:
            self._seen_ids = set(list(self._seen_ids)[-25_000:])
        return result

    # ── Stage 1 ───────────────────────────────────────────────────────────────

    async def discover_trends(self, max_trends: int = 15) -> list[TrendTopic]:
        """Discover current Lebanon trending topics.

        Returns up to max_trends topics, always including the curated Tier-1
        hashtags even when the X API returns live trends (to ensure coverage).
        """
        topics = await self._twscrape.discover_trends(LEBANON_WOEID)

        # Always augment with curated Tier-1 hashtags if not already present
        existing_names = {t.name.lower() for t in topics}
        next_rank = (topics[-1].trend_rank + 1) if topics else 1
        for tag in CURATED_LB_HASHTAGS_TIER1:
            tag_clean = tag.lstrip("#")
            if tag_clean.lower() not in existing_names:
                topics.append(TrendTopic(
                    name=tag_clean,
                    display_name=f"#{tag_clean}",
                    tweet_volume=None,
                    trend_rank=next_rank,
                    source="curated",
                ))
                next_rank += 1

        self._last_trends = topics[:max_trends]
        logger.info(
            "Trend discovery: %d topics (top: %s)",
            len(self._last_trends),
            [t.display_name for t in self._last_trends[:5]],
        )
        return self._last_trends

    # ── Stage 2 ───────────────────────────────────────────────────────────────

    async def scrape_for_trends(
        self,
        trends: list[TrendTopic],
        tweets_per_trend: int = 20,
        use_account_fallback: bool = False,
    ) -> list[ScrapedPost]:
        """Scrape top tweets for each trend using SearchTimeline GraphQL.

        For each trend calls search_hashtag_top() (SearchTimeline with product=Top).

        When use_account_fallback=False (default), returns an empty list if
        SearchTimeline fails — the caller (run_scan) then falls through to the
        public keyword scan stage. This prevents any fallback to the fixed
        14-account list.

        When use_account_fallback=True, falls back to _timeline_trend_index()
        (the old behaviour — account timelines tagged by trend match).
        """
        all_posts: list[ScrapedPost] = []
        search_worked = False

        for trend in trends:
            posts = await self._twscrape.search_hashtag_top(trend, limit=tweets_per_trend)
            if posts:
                search_worked = True
                all_posts.extend(posts)
                logger.info(
                    "Trend #%s (rank %d, src=%s) → %d posts",
                    trend.name, trend.trend_rank, trend.source, len(posts),
                )
            await asyncio.sleep(0.8)

        if not search_worked:
            if use_account_fallback:
                logger.info(
                    "SearchTimeline returned 0 for all %d trends — falling back to timeline indexing",
                    len(trends),
                )
                all_posts = await self._timeline_trend_index(trends, limit_per_account=20)
            else:
                logger.info(
                    "SearchTimeline returned 0 for all %d trends — skipping account fallback "
                    "(public keyword scan will run as Stage 2 in run_scan)",
                    len(trends),
                )

        deduped = self._dedup(all_posts)
        # Sort by engagement velocity descending (most viral first)
        deduped.sort(key=lambda p: p.engagement_velocity, reverse=True)
        return deduped

    async def _timeline_trend_index(
        self,
        trends: list[TrendTopic],
        limit_per_account: int = 40,
        max_age_hours: int = 48,
    ) -> list[ScrapedPost]:
        """Fallback: scrape influencer timelines, tag posts by matching trend.

        Matching strategy (first match wins):
          1. Post hashtags match a trend name
          2. Post content contains the trend name or keyword
        Only posts from the last max_age_hours are kept.
        """
        timeline_posts = await self.scrape_media_timelines(
            limit_per_account=limit_per_account,
            min_engagement=0,
            max_age_hours=max_age_hours,
        )
        # Build lookup: lowercase trend name (no #) → TrendTopic
        trend_names = {t.name.lower().lstrip("#"): t for t in trends}
        # Also map display_name variants
        for t in trends:
            dn = t.display_name.lower().lstrip("#")
            if dn not in trend_names:
                trend_names[dn] = t

        for post in timeline_posts:
            if post.matched_trend:
                continue

            content_lower = post.content.lower()

            # 1. Match on post hashtags
            for tag in post.hashtags:
                tag_clean = tag.lower().lstrip("#")
                if tag_clean in trend_names:
                    t = trend_names[tag_clean]
                    post.matched_trend = t.name
                    post.compute_engagement_velocity()
                    break

            # 2. Match on content keyword (trend name appears anywhere in text)
            if not post.matched_trend:
                for trend_key, t in trend_names.items():
                    if trend_key and trend_key in content_lower:
                        post.matched_trend = t.name
                        post.compute_engagement_velocity()
                        break

            # 3. Fallback: tag as generic Lebanon content
            if not post.matched_trend:
                post.matched_trend = "لبنان"
                post.compute_engagement_velocity()

        matched = sum(1 for p in timeline_posts if p.matched_trend and p.matched_trend != "لبنان")
        logger.info(
            "Timeline index: %d fresh posts, %d matched to specific trends, %d tagged generic",
            len(timeline_posts), matched, len(timeline_posts) - matched,
        )
        return timeline_posts

    # ── Convenience wrappers ──────────────────────────────────────────────────

    async def scrape_trending(
        self,
        max_hashtags: int = 15,
        tweets_per_tag: int = 20,
    ) -> list[ScrapedPost]:
        """Full trend-first pipeline: discover trends → scrape tweets."""
        trends = await self.discover_trends(max_trends=max_hashtags)
        return await self.scrape_for_trends(trends, tweets_per_trend=tweets_per_tag)

    async def scrape_public_keywords(
        self,
        queries: list[str] | None = None,
        limit_per_query: int = 20,
    ) -> list[ScrapedPost]:
        """Public broadcast keyword scan using guest token API (no account needed).

        Unlike scrape_queries() which tries authenticated SearchTimeline first,
        this method uses ONLY the XGuestScraper for truly public broad discovery.
        It searches ALL public X posts, not just posts from specific accounts.

        Used as the primary fallback when authenticated trend search fails.
        Covers hate speech keywords in Arabic, English, and French.
        """
        targets = queries or PUBLIC_HATE_SPEECH_QUERIES
        all_posts: list[ScrapedPost] = []

        for query in targets:
            posts = await self._guest.search(query, limit=limit_per_query)
            for post in posts:
                # Tag with the first word of the query as matched_trend
                tag = query.lstrip("#").split()[0] if query.strip() else "لبنان"
                post.matched_trend = tag
                post.compute_engagement_velocity()
            all_posts.extend(posts)
            await asyncio.sleep(1.0)  # respect guest API rate limits

        deduped = self._dedup(all_posts)
        logger.info(
            "Public keyword scan: %d queries → %d unique posts (guest API)",
            len(targets),
            len(deduped),
        )
        return deduped

    async def scrape_queries(
        self,
        queries: list[str] | None = None,
        limit_per_query: int = 30,
    ) -> list[ScrapedPost]:
        """Run seed queries — keyword-based fallback."""
        targets = queries or SEED_QUERIES
        all_posts: list[ScrapedPost] = []
        for query in targets:
            posts = await self._twscrape.search_hashtag_top(
                TrendTopic(name=query, display_name=query, tweet_volume=None, trend_rank=99, source="keyword"),
                limit=limit_per_query,
            )
            if not posts:
                posts = await self._guest.search(query, limit=limit_per_query)
            all_posts.extend(posts)
            await asyncio.sleep(1.5)
        return self._dedup(all_posts)

    async def scrape_media_timelines(
        self,
        limit_per_account: int = 30,
        min_engagement: int = 0,
        max_age_hours: int = 48,
    ) -> list[ScrapedPost]:
        """Fetch tweets from Lebanese influencer accounts (account-based fallback).

        Only returns posts from the last `max_age_hours` hours (default 48h).
        This prevents old timeline posts from surfacing as "current" content.

        NOTE: Does NOT call self._dedup so that callers (scrape_for_trends) can do
        the single authoritative dedup. Using a local set for within-call uniqueness only.
        """
        all_posts: list[ScrapedPost] = []
        seen_local: set[str] = set()
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)

        for handle in LEBANESE_INFLUENCER_ACCOUNTS:
            posts = await self._twscrape.fetch_user_timeline(handle, limit=limit_per_account)
            # Drop posts older than max_age_hours
            fresh = [p for p in posts if p.posted_at >= cutoff]
            stale = len(posts) - len(fresh)
            if stale:
                logger.info("Timeline @%s: dropped %d stale posts (>%dh old)", handle, stale, max_age_hours)
            posts = fresh
            if min_engagement > 0:
                posts = [p for p in posts if p.engagement_total >= min_engagement]
            # Local dedup only (don't touch self._seen_ids yet)
            posts = [p for p in posts if p.post_id not in seen_local]
            seen_local.update(p.post_id for p in posts)
            if posts:
                logger.info("Timeline @%s → %d fresh posts (last %dh)", handle, len(posts), max_age_hours)
            else:
                logger.info("Timeline @%s → 0 fresh posts", handle)
            all_posts.extend(posts)
            await asyncio.sleep(2.5)  # 2.5s gap to stay within X rate limits
        return all_posts

    async def fetch_tweet_replies(self, tweet_id: str, limit: int = 10) -> list[ScrapedPost]:
        """Return the most-liked replies to a tweet."""
        return await self._twscrape.fetch_tweet_replies(tweet_id, limit=limit)

    @property
    def last_trends(self) -> list[TrendTopic]:
        """The most recently discovered trend topics (cached between scans)."""
        return self._last_trends


# ── Singleton ─────────────────────────────────────────────────────────────────

x_scraper_service = XScraperService()
