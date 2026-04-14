"""X (Twitter) Scraper Service for Hate Speech Monitoring.

Uses twscrape (no API key required — uses X accounts via internal API).
Falls back to httpx-based guest-token scraping when twscrape accounts
are not configured.

Searches for Lebanese political/hate speech content across:
  1. Seed keywords (sectarian, political, refugee topics)
  2. Reply threads of major Lebanese media accounts
  3. Trending Lebanese hashtags

Each scraped post is passed to hate_speech_detector for analysis.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)

# ── Lebanese media accounts to monitor replies of ────────────────────────────

LEBANESE_MEDIA_ACCOUNTS = [
    "LBCI_News",
    "MTV_Lebanon",
    "NaharnetAr",
    "AlJumhuriya",
    "dailystarleb",
    "lorientlejour",
    "961Lebanon",
]

# ── Seed search queries — Lebanon hate speech signals ────────────────────────
# Mix of Arabic, English, French terms around Lebanese political/sectarian content

SEED_QUERIES = [
    # Sectarian — Arabic
    "لبنان طائفية -filter:links",
    "حزب الله مسيحيين OR سنة OR درزية",
    "شيعة سنة لبنان",
    # Refugee incitement — Arabic
    "اللاجئين السوريين لبنان ارحلوا OR اخرجوا OR طردهم",
    "النازحين لبنان",
    # Political incitement — Arabic/English
    "لبنان يستحق الموت OR اغتيال OR تصفية",
    "lebanon sectarian hate",
    "lebanon militia attack",
    # French
    "liban réfugiés sectaire",
    "liban haine politique",
]

# ── X Guest Token Scraper (no account needed, limited) ───────────────────────

_GUEST_TOKEN_URL = "https://api.twitter.com/1.1/guest/activate.json"
_SEARCH_URL = "https://twitter.com/i/api/2/search/adaptive.json"

_X_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)


@dataclass
class ScrapedPost:
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

    @property
    def account_age_days(self) -> int | None:
        if self.author_created_at is None:
            return None
        return (datetime.now(UTC) - self.author_created_at).days

    @property
    def engagement_total(self) -> int:
        return self.like_count + self.retweet_count + self.reply_count + self.quote_count


class XGuestScraper:
    """Scrapes X search results using the guest token endpoint.
    No account required. Limited to ~150 results per query per hour.
    """

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

            # Strip URLs from content for analysis (keep text only)
            clean_content = re.sub(r"http\S+", "", content).strip()

            author_handle = user.get("screen_name", "")
            author_id = user.get("id_str", "")
            author_created_raw = user.get("created_at", "")
            author_created_at: datetime | None = None
            if author_created_raw:
                try:
                    author_created_at = datetime.strptime(
                        author_created_raw, "%a %b %d %H:%M:%S +0000 %Y"
                    ).replace(tzinfo=UTC)
                except ValueError:
                    pass

            posted_raw = legacy.get("created_at", "")
            posted_at = datetime.now(UTC)
            if posted_raw:
                try:
                    posted_at = datetime.strptime(
                        posted_raw, "%a %b %d %H:%M:%S +0000 %Y"
                    ).replace(tzinfo=UTC)
                except ValueError:
                    pass

            hashtags = [
                ht.get("text", "").lower()
                for ht in legacy.get("entities", {}).get("hashtags", [])
            ]

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
                # Walk the timeline entries
                timeline = (
                    data.get("timeline", {})
                    .get("instructions", [{}])[0]
                    .get("addEntries", {})
                    .get("entries", [])
                )
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

                    user_created_raw = user.get("created_at", "")
                    if user_created_raw:
                        try:
                            post.author_created_at = datetime.strptime(
                                user_created_raw, "%a %b %d %H:%M:%S +0000 %Y"
                            ).replace(tzinfo=UTC)
                        except ValueError:
                            pass

                    if post.content:
                        posts.append(post)

        except Exception as exc:
            logger.warning("X guest scrape failed for '%s': %s", query, exc)

        return posts


class TwscrapeScraper:
    """Uses twscrape library (requires X accounts configured via CLI).
    Higher quality results, real tweet data including replies.
    """

    def __init__(self) -> None:
        self._api: object | None = None
        self._loaded = False

    def _load(self) -> bool:
        if self._loaded:
            return self._api is not None
        try:
            import os
            from twscrape import API  # type: ignore[import]
            # Look for accounts DB in /app (Docker mount) or local fallback
            db_candidates = [
                "/app/twscrape_accounts.db",
                os.path.join(os.path.dirname(__file__), "../../../../twscrape_accounts.db"),
                os.path.expanduser("~/.local/share/twscrape/accounts.db"),
            ]
            db_path = next((p for p in db_candidates if os.path.exists(p)), None)
            if db_path:
                logger.info("twscrape using DB: %s", db_path)
                self._api = API(db_path)
            else:
                self._api = API()
            self._loaded = True
            logger.info("twscrape API loaded")
            return True
        except ImportError:
            logger.info("twscrape not installed — using guest scraper only")
            self._api = None
            self._loaded = True
            return False

    async def search(self, query: str, limit: int = 50) -> list[ScrapedPost]:
        if not self._load() or self._api is None:
            return []
        posts: list[ScrapedPost] = []
        try:
            async for tweet in self._api.search(query, limit=limit):  # type: ignore[attr-defined]
                post = ScrapedPost(
                    post_id=str(tweet.id),
                    author_id=str(tweet.user.id),
                    author_handle=tweet.user.username,
                    author_created_at=tweet.user.created.replace(tzinfo=UTC) if tweet.user.created else None,
                    content=re.sub(r"http\S+", "", tweet.rawContent or "").strip(),
                    lang=tweet.lang or "",
                    like_count=tweet.likeCount or 0,
                    retweet_count=tweet.retweetCount or 0,
                    reply_count=tweet.replyCount or 0,
                    quote_count=tweet.quoteCount or 0,
                    posted_at=tweet.date.replace(tzinfo=UTC) if tweet.date else datetime.now(UTC),
                    source_url=tweet.url or f"https://twitter.com/{tweet.user.username}/status/{tweet.id}",
                    in_reply_to_id=str(tweet.inReplyToTweetId) if tweet.inReplyToTweetId else None,
                    hashtags=[ht.lower() for ht in (tweet.hashtags or [])],
                )
                if post.content:
                    posts.append(post)
        except Exception as exc:
            logger.warning("twscrape search failed for '%s': %s", query, exc)
        return posts


class XScraperService:
    """Unified X scraping service — tries twscrape first, falls back to guest."""

    def __init__(self) -> None:
        self._twscrape = TwscrapeScraper()
        self._guest = XGuestScraper()
        self._seen_ids: set[str] = set()

    def _dedup(self, posts: list[ScrapedPost]) -> list[ScrapedPost]:
        result = []
        for p in posts:
            if p.post_id not in self._seen_ids:
                self._seen_ids.add(p.post_id)
                result.append(p)
        # Keep seen_ids from growing unbounded
        if len(self._seen_ids) > 50_000:
            self._seen_ids = set(list(self._seen_ids)[-25_000:])
        return result

    async def scrape_queries(self, queries: list[str] | None = None, limit_per_query: int = 30) -> list[ScrapedPost]:
        """Run all seed queries and return deduplicated posts."""
        targets = queries or SEED_QUERIES
        all_posts: list[ScrapedPost] = []

        for query in targets:
            # Try twscrape first
            posts = await self._twscrape.search(query, limit=limit_per_query)
            if not posts:
                # Fall back to guest
                posts = await self._guest.search(query, limit=limit_per_query)

            all_posts.extend(posts)
            await asyncio.sleep(1.5)  # Polite delay between queries

        return self._dedup(all_posts)

    async def scrape_media_replies(self, limit_per_account: int = 20) -> list[ScrapedPost]:
        """Scrape reply threads of major Lebanese media accounts."""
        all_posts: list[ScrapedPost] = []
        for handle in LEBANESE_MEDIA_ACCOUNTS:
            query = f"to:{handle} lang:ar OR lang:en OR lang:fr"
            posts = await self._twscrape.search(query, limit=limit_per_account)
            if not posts:
                posts = await self._guest.search(query, limit=limit_per_account)
            all_posts.extend(posts)
            await asyncio.sleep(1.5)
        return self._dedup(all_posts)


x_scraper_service = XScraperService()
