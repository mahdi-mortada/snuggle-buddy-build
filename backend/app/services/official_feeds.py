from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import unescape
import json
import re
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

import httpx

from app.config import get_settings


@dataclass(slots=True)
class OfficialFeedAccount:
    publisher_name: str
    publisher_type: str
    credibility: str
    credibility_score: float
    initials: str
    platform: str
    handle: str
    account_label: str
    account_url: str
    feed_url: str


@dataclass(slots=True)
class OfficialFeedPost:
    id: str
    platform: str
    publisher_name: str
    account_label: str
    account_handle: str
    account_url: str
    post_url: str
    content: str
    signal_tags: list[str]
    source_info: dict[str, object]
    published_at: datetime


OFFICIAL_FEED_ACCOUNTS: tuple[OfficialFeedAccount, ...] = (
    OfficialFeedAccount(
        publisher_name="LBCI",
        publisher_type="tv",
        credibility="verified",
        credibility_score=88,
        initials="LB",
        platform="telegram",
        handle="LBCI_NEWS",
        account_label="LBCI News Wire",
        account_url="https://t.me/LBCI_NEWS",
        feed_url="https://t.me/s/LBCI_NEWS",
    ),
    OfficialFeedAccount(
        publisher_name="MTV Lebanon",
        publisher_type="tv",
        credibility="high",
        credibility_score=84,
        initials="MT",
        platform="telegram",
        handle="MTVLebanoNews",
        account_label="MTV Lebanon News",
        account_url="https://t.me/MTVLebanoNews",
        feed_url="https://t.me/s/MTVLebanoNews",
    ),
    OfficialFeedAccount(
        publisher_name="Al Jadeed",
        publisher_type="tv",
        credibility="high",
        credibility_score=82,
        initials="AJ",
        platform="telegram",
        handle="Aljadeedtelegram",
        account_label="Al Jadeed News",
        account_url="https://t.me/Aljadeedtelegram",
        feed_url="https://t.me/s/Aljadeedtelegram",
    ),
    OfficialFeedAccount(
        publisher_name="Al Manar",
        publisher_type="tv",
        credibility="high",
        credibility_score=80,
        initials="AM",
        platform="telegram",
        handle="almanarnews",
        account_label="Al Manar TV",
        account_url="https://t.me/almanarnews",
        feed_url="https://t.me/s/almanarnews",
    ),
)

KEYWORD_TAGS: tuple[str, ...] = (
    "lebanon",
    "beirut",
    "security",
    "attack",
    "strike",
    "airport",
    "explosion",
    "parliament",
    "government",
    "south",
    "border",
    "unifil",
    "protest",
    "outage",
    "hospital",
)


class OfficialFeedService:
    def __init__(self) -> None:
        self._cache: list[OfficialFeedPost] = []
        self._cached_at: datetime | None = None
        self._cache_ttl = timedelta(minutes=3)

    async def fetch_posts(self, limit: int | None = None) -> list[OfficialFeedPost]:
        settings = get_settings()
        if not settings.official_feeds_enabled:
            return []

        requested_limit = self._sanitize_limit(limit if limit is not None else settings.official_feed_limit, default=50)
        window_hours = self._window_hours(settings.live_news_window_hours)
        now = datetime.now(UTC)
        if self._cached_at and now - self._cached_at < self._cache_ttl:
            recent_cached = self._filter_recent_posts(self._cache, now=now, window_hours=window_hours)
            return recent_cached[:requested_limit]

        posts: list[OfficialFeedPost] = []
        accounts = self._accounts(settings)
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "CrisisShield/1.0 (+local-dev)"},
        ) as client:
            for account in accounts:
                try:
                    response = await client.get(account.feed_url)
                    response.raise_for_status()
                except httpx.HTTPError:
                    continue
                posts.extend(self._parse_telegram_channel(account, response.text))

        posts.sort(key=lambda item: item.published_at, reverse=True)
        deduped = self._dedupe_posts(posts)
        recent_posts = self._filter_recent_posts(deduped, now=now, window_hours=window_hours)
        self._cache = recent_posts
        self._cached_at = now
        return recent_posts[:requested_limit]

    def _window_hours(self, configured_window: int | None) -> int:
        if not isinstance(configured_window, int):
            return 24
        return max(1, configured_window)

    def _sanitize_limit(self, requested_limit: int | None, *, default: int) -> int:
        if not isinstance(requested_limit, int):
            return default
        return max(1, min(100, requested_limit))

    def _filter_recent_posts(
        self,
        posts: list[OfficialFeedPost],
        *,
        now: datetime,
        window_hours: int,
    ) -> list[OfficialFeedPost]:
        cutoff = now - timedelta(hours=window_hours)
        recent_posts: list[OfficialFeedPost] = []

        for post in posts:
            published_at = getattr(post, "published_at", None)
            if not isinstance(published_at, datetime):
                continue
            try:
                published_at_utc = published_at if published_at.tzinfo is not None else published_at.replace(tzinfo=UTC)
                published_at_utc = published_at_utc.astimezone(UTC)
            except (ValueError, TypeError):
                continue
            if published_at_utc < cutoff:
                continue
            recent_posts.append(post)

        recent_posts.sort(
            key=lambda item: item.published_at if item.published_at.tzinfo is not None else item.published_at.replace(tzinfo=UTC),
            reverse=True,
        )
        return recent_posts

    def _accounts(self, settings) -> list[OfficialFeedAccount]:
        accounts = list(OFFICIAL_FEED_ACCOUNTS)
        extra_config = settings.official_feed_extra_channels_json.strip()
        if not extra_config:
            return accounts

        try:
            raw_accounts = json.loads(extra_config)
        except json.JSONDecodeError:
            return accounts

        if not isinstance(raw_accounts, list):
            return accounts

        for item in raw_accounts:
            account = self._account_from_mapping(item)
            if account is not None:
                accounts.append(account)

        return accounts

    def _account_from_mapping(self, item: object) -> OfficialFeedAccount | None:
        if not isinstance(item, dict):
            return None

        platform = str(item.get("platform", "telegram")).strip().lower()
        handle = str(item.get("handle", "")).strip().lstrip("@")
        publisher_name = str(item.get("publisher_name", "")).strip()
        account_label = str(item.get("account_label", publisher_name)).strip() or publisher_name
        publisher_type = str(item.get("publisher_type", "social_media")).strip() or "social_media"
        credibility = str(item.get("credibility", "moderate")).strip() or "moderate"
        initials = str(item.get("initials", publisher_name[:2].upper())).strip() or "OF"

        if not publisher_name or not handle:
            return None

        try:
            credibility_score = float(item.get("credibility_score", 60))
        except (TypeError, ValueError):
            credibility_score = 60.0

        account_url = str(item.get("account_url", f"https://t.me/{handle}")).strip() or f"https://t.me/{handle}"
        feed_url = str(item.get("feed_url", f"https://t.me/s/{handle}")).strip() or f"https://t.me/s/{handle}"

        return OfficialFeedAccount(
            publisher_name=publisher_name,
            publisher_type=publisher_type,
            credibility=credibility,
            credibility_score=credibility_score,
            initials=initials,
            platform=platform,
            handle=handle,
            account_label=account_label,
            account_url=account_url,
            feed_url=feed_url,
        )

    def _parse_telegram_channel(self, account: OfficialFeedAccount, html_text: str) -> list[OfficialFeedPost]:
        posts: list[OfficialFeedPost] = []
        pattern = re.compile(
            r'<div class="tgme_widget_message_wrap js-widget_message_wrap">(?P<block>.*?)</div></div>(?=(?:<div class="tgme_widget_message_wrap js-widget_message_wrap">)|(?:\s*</section>))',
            flags=re.DOTALL,
        )

        for match in pattern.finditer(html_text):
            block = match.group("block")
            post_match = re.search(r'data-post="([^"]+)"', block)
            date_match = re.search(r'<time[^>]+datetime="([^"]+)"', block)
            text_match = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, flags=re.DOTALL)
            link_match = re.search(r'<a class="tgme_widget_message_date" href="([^"]+)"', block)

            if not post_match or not date_match or not link_match:
                continue

            content = self._clean_html(text_match.group(1) if text_match else "")
            if not content:
                continue

            published_at = self._parse_datetime(date_match.group(1))
            if published_at is None:
                continue

            post_url = unescape(link_match.group(1))
            if post_url.startswith("/"):
                post_url = f"https://t.me{post_url}"

            posts.append(
                OfficialFeedPost(
                    id=f"official-feed-{uuid5(NAMESPACE_URL, post_url)}",
                    platform=account.platform,
                    publisher_name=account.publisher_name,
                    account_label=account.account_label,
                    account_handle=account.handle,
                    account_url=account.account_url,
                    post_url=post_url,
                    content=content,
                    signal_tags=self._extract_tags(content),
                    source_info={
                        "name": account.publisher_name,
                        "type": account.publisher_type,
                        "credibility": account.credibility,
                        "credibilityScore": account.credibility_score,
                        "logoInitials": account.initials,
                        "url": account.account_url,
                        "verifiedBy": [],
                    },
                    published_at=published_at,
                )
            )

            if len(posts) >= 12:
                break

        return posts

    def _clean_html(self, html_fragment: str) -> str:
        fragment = re.sub(r"<br\s*/?>", "\n", html_fragment, flags=re.IGNORECASE)
        fragment = re.sub(r"</p>", "\n", fragment, flags=re.IGNORECASE)
        fragment = re.sub(r"<[^>]+>", " ", fragment)
        fragment = unescape(fragment)
        fragment = fragment.replace("\u200f", "").replace("\u200e", "").replace("\ufeff", "")
        lines = [re.sub(r"\s+", " ", line).strip() for line in fragment.splitlines()]
        collapsed = "\n".join(line for line in lines if line)
        return collapsed.strip()

    def _parse_datetime(self, value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _extract_tags(self, content: str) -> list[str]:
        lowered = content.lower()
        tags = [tag for tag in KEYWORD_TAGS if tag in lowered]
        hashtags = [match.group(1).lower() for match in re.finditer(r"#([\w\u0600-\u06ff]+)", content)]
        for tag in hashtags:
            if tag not in tags:
                tags.append(tag)
        return tags[:6]

    def _dedupe_posts(self, posts: list[OfficialFeedPost]) -> list[OfficialFeedPost]:
        seen_signatures: set[str] = set()
        unique_posts: list[OfficialFeedPost] = []

        for post in posts:
            signature = self._signature(post.content, post.post_url)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            unique_posts.append(post)

        return unique_posts

    def _signature(self, content: str, post_url: str) -> str:
        normalized = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", content.lower()).strip()
        if normalized:
            return normalized[:180]
        path = urlparse(post_url).path.lower().strip("/")
        return path


official_feed_service = OfficialFeedService()
