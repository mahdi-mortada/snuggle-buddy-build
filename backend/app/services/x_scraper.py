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
import os
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

    Note: X restricts keyword search for accounts without phone verification.
    This scraper uses user_tweets() to pull from monitored accounts' timelines,
    which works reliably without elevated access.
    """

    def __init__(self) -> None:
        self._api: object | None = None
        self._loaded = False
        self._user_id_cache: dict[str, int] = {}

    def _load(self) -> bool:
        if self._loaded:
            return self._api is not None
        try:
            import os
            from twscrape import API  # type: ignore[import]
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

    def _tweet_to_post(self, tweet: object) -> ScrapedPost | None:
        try:
            return ScrapedPost(
                post_id=str(tweet.id),  # type: ignore[attr-defined]
                author_id=str(tweet.user.id),  # type: ignore[attr-defined]
                author_handle=tweet.user.username,  # type: ignore[attr-defined]
                author_created_at=tweet.user.created.replace(tzinfo=UTC) if tweet.user.created else None,  # type: ignore[attr-defined]
                content=re.sub(r"http\S+", "", tweet.rawContent or "").strip(),  # type: ignore[attr-defined]
                lang=tweet.lang or "",  # type: ignore[attr-defined]
                like_count=tweet.likeCount or 0,  # type: ignore[attr-defined]
                retweet_count=tweet.retweetCount or 0,  # type: ignore[attr-defined]
                reply_count=tweet.replyCount or 0,  # type: ignore[attr-defined]
                quote_count=tweet.quoteCount or 0,  # type: ignore[attr-defined]
                posted_at=tweet.date.replace(tzinfo=UTC) if tweet.date else datetime.now(UTC),  # type: ignore[attr-defined]
                source_url=tweet.url or f"https://twitter.com/{tweet.user.username}/status/{tweet.id}",  # type: ignore[attr-defined]
                in_reply_to_id=str(tweet.inReplyToTweetId) if tweet.inReplyToTweetId else None,  # type: ignore[attr-defined]
                hashtags=[ht.lower() for ht in (tweet.hashtags or [])],  # type: ignore[attr-defined]
            )
        except Exception as exc:
            logger.debug("Could not convert tweet to post: %s", exc)
            return None

    async def search(self, query: str, limit: int = 50) -> list[ScrapedPost]:
        """Attempt keyword search. Falls back to empty list if search is restricted."""
        if not self._load() or self._api is None:
            return []
        posts: list[ScrapedPost] = []
        try:
            async for tweet in self._api.search(query, limit=limit):  # type: ignore[attr-defined]
                post = self._tweet_to_post(tweet)
                if post and post.content:
                    posts.append(post)
        except Exception as exc:
            logger.warning("twscrape search failed for '%s': %s", query, exc)
        return posts

    async def prewarm_xclid(self) -> bool:
        """Pre-generate XClientTxId so the first API call doesn't timeout."""
        try:
            from twscrape.xclid import XClIdGen  # type: ignore[import]
            from twscrape.queue_client import XClIdGenStore  # type: ignore[import]
            gen = await XClIdGen.create()
            # Cache for all accounts in the pool
            if not self._load() or self._api is None:
                return False
            accounts = await self._api.pool.get_all()  # type: ignore[attr-defined]
            for acc in accounts:
                XClIdGenStore.items[acc.username] = gen
            logger.info("twscrape: XClientTxId pre-warmed for %d account(s)", len(accounts))
            return True
        except Exception as exc:
            logger.warning("twscrape: XClientTxId pre-warm failed: %s", exc)
            return False

    # ── Direct HTTP timeline fetcher (bypasses queue client locking issues) ──

    async def fetch_user_timeline(self, handle: str, limit: int = 30) -> list[ScrapedPost]:
        """Fetch a user's recent tweets via direct X GraphQL calls.

        Bypasses twscrape's queue client entirely to avoid account-lock issues.
        Uses the cached XClientTxId from XClIdGenStore if available.
        """
        if not self._load() or self._api is None:
            return []

        try:
            import json as _json
            import sqlite3 as _sqlite3

            # Read cookies from DB directly
            db_candidates = [
                "/app/twscrape_accounts.db",
                os.path.join(os.path.dirname(__file__), "../../../../twscrape_accounts.db"),
                os.path.expanduser("~/.local/share/twscrape/accounts.db"),
            ]
            db_path = next((p for p in db_candidates if os.path.exists(p)), None)
            if not db_path:
                return []

            conn = _sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT username, cookies FROM accounts WHERE active=1 LIMIT 1")
            row = cur.fetchone()
            conn.close()
            if not row:
                return []

            username, cookies_json = row
            cookies: dict = _json.loads(cookies_json) if cookies_json else {}
            if not cookies.get("auth_token"):
                return []

            # Get XClientTxId (use cache or generate fresh)
            from twscrape.xclid import XClIdGen  # type: ignore[import]
            from twscrape.queue_client import XClIdGenStore  # type: ignore[import]
            if username not in XClIdGenStore.items:
                try:
                    gen = await XClIdGen.create()
                    XClIdGenStore.items[username] = gen
                except Exception as exc:
                    logger.warning("XClIdGen.create() failed, proceeding without txid: %s", exc)
                    XClIdGenStore.items[username] = None  # type: ignore[assignment]

            gen = XClIdGenStore.items.get(username)

            _BEARER = (
                "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
                "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
            )
            base_headers = {
                "Authorization": f"Bearer {_BEARER}",
                "x-csrf-token": cookies.get("ct0", ""),
                "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
                "x-twitter-active-user": "yes",
                "x-twitter-auth-type": "OAuth2Session",
                "x-twitter-client-language": "en",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://x.com/",
                "Origin": "https://x.com",
            }

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
                        ub_headers["x-client-transaction-id"] = gen.calc("GET", ub_path)
                    resp = await client.get(
                        f"https://x.com{ub_path}",
                        params={
                            "variables": _json.dumps({"screen_name": handle, "withSafetyModeUserFields": True}),
                            "features": _json.dumps({"hidden_profile_likes_enabled": True, "hidden_profile_subscriptions_enabled": True}),
                        },
                        headers=ub_headers,
                    )
                    if resp.status_code != 200:
                        logger.debug("UserByScreenName %s: %d", handle, resp.status_code)
                        return []
                    result = resp.json().get("data", {}).get("user", {}).get("result", {})
                    user_id = result.get("rest_id") or result.get("legacy", {}).get("id_str")
                    screen_name = result.get("legacy", {}).get("screen_name", handle)
                    if not user_id:
                        return []
                    self._user_id_cache[handle] = user_id  # type: ignore[assignment]

                # Step 2: fetch user tweets
                from twscrape.api import GQL_FEATURES  # type: ignore[import]
                from twscrape.api import OP_UserTweets  # type: ignore[import]
                ut_path = f"/i/api/graphql/{OP_UserTweets}"
                ut_headers = {**base_headers}
                if gen:
                    ut_headers["x-client-transaction-id"] = gen.calc("GET", ut_path)

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
                if resp2.status_code != 200:
                    logger.debug("UserTweets %s: %d", handle, resp2.status_code)
                    return []

                data = resp2.json()
                entries = []
                # Walk the nested timeline structure
                # X returns either timeline_v2 or timeline depending on the features flags
                user_result = data.get("data", {}).get("user", {}).get("result", {})
                tl = user_result.get("timeline_v2") or user_result.get("timeline") or {}
                instructions = tl.get("timeline", {}).get("instructions", [])
                for instruction in instructions:
                    entries.extend(instruction.get("entries", []))

                posts: list[ScrapedPost] = []
                now = datetime.now(UTC)
                for entry in entries:
                    try:
                        tweet_data = (
                            entry.get("content", {})
                            .get("itemContent", {})
                            .get("tweet_results", {})
                            .get("result", {})
                        )
                        if not tweet_data or tweet_data.get("__typename") != "Tweet":
                            continue
                        legacy = tweet_data.get("legacy", {})
                        user_legacy = (
                            tweet_data.get("core", {})
                            .get("user_results", {})
                            .get("result", {})
                            .get("legacy", {})
                        )
                        content = re.sub(r"http\S+", "", legacy.get("full_text", "")).strip()
                        if not content:
                            continue
                        post_id = legacy.get("id_str", "")
                        posted_raw = legacy.get("created_at", "")
                        posted_at = now
                        if posted_raw:
                            try:
                                posted_at = datetime.strptime(posted_raw, "%a %b %d %H:%M:%S +0000 %Y").replace(tzinfo=UTC)
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
                        posts.append(ScrapedPost(
                            post_id=post_id,
                            author_id=user_legacy.get("id_str", ""),
                            author_handle=user_legacy.get("screen_name", screen_name),
                            author_created_at=author_created_at,
                            content=content,
                            lang=legacy.get("lang", ""),
                            like_count=int(legacy.get("favorite_count", 0)),
                            retweet_count=int(legacy.get("retweet_count", 0)),
                            reply_count=int(legacy.get("reply_count", 0)),
                            quote_count=int(legacy.get("quote_count", 0)),
                            posted_at=posted_at,
                            source_url=f"https://x.com/{user_legacy.get('screen_name', screen_name)}/status/{post_id}",
                            in_reply_to_id=legacy.get("in_reply_to_status_id_str"),
                            hashtags=[ht.get("text", "").lower() for ht in legacy.get("entities", {}).get("hashtags", [])],
                        ))
                        if len(posts) >= limit:
                            break
                    except Exception as exc:
                        logger.debug("Tweet parse error: %s", exc)
                        continue

                logger.info("Direct fetch @%s: %d tweets", handle, len(posts))
                return posts

        except Exception as exc:
            logger.warning("Direct fetch_user_timeline failed for @%s: %s", handle, exc)
            return []


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
        """Run seed queries — tries keyword search first, falls back to guest scraper."""
        targets = queries or SEED_QUERIES
        all_posts: list[ScrapedPost] = []

        for query in targets:
            posts = await self._twscrape.search(query, limit=limit_per_query)
            if not posts:
                posts = await self._guest.search(query, limit=limit_per_query)
            all_posts.extend(posts)
            await asyncio.sleep(1.5)

        return self._dedup(all_posts)

    async def scrape_media_timelines(self, limit_per_account: int = 30) -> list[ScrapedPost]:
        """Fetch recent tweets from Lebanese media accounts using user_tweets().

        This works reliably even without X search access, as it uses the
        user timeline endpoint which requires only basic authentication.
        """
        all_posts: list[ScrapedPost] = []
        for handle in LEBANESE_MEDIA_ACCOUNTS:
            posts = await self._twscrape.fetch_user_timeline(handle, limit=limit_per_account)
            if posts:
                logger.info("twscrape: fetched %d posts from @%s", len(posts), handle)
            else:
                logger.debug("twscrape: no posts from @%s (trying guest)", handle)
            all_posts.extend(posts)
            await asyncio.sleep(1.5)
        return self._dedup(all_posts)

    async def scrape_media_replies(self, limit_per_account: int = 20) -> list[ScrapedPost]:
        """Scrape reply threads of major Lebanese media accounts.

        Tries user_tweets (reliable) then falls back to guest search.
        """
        # Primary: use timeline (works without search access)
        all_posts = await self.scrape_media_timelines(limit_per_account=limit_per_account)
        if all_posts:
            return all_posts

        # Fallback: try search-based approach
        for handle in LEBANESE_MEDIA_ACCOUNTS:
            query = f"to:{handle} lang:ar OR lang:en OR lang:fr"
            posts = await self._twscrape.search(query, limit=limit_per_account)
            if not posts:
                posts = await self._guest.search(query, limit=limit_per_account)
            all_posts.extend(posts)
            await asyncio.sleep(1.5)
        return self._dedup(all_posts)


x_scraper_service = XScraperService()
