from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from html import unescape
import logging
import re
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

import httpx

logger = logging.getLogger(__name__)

from app.config import get_settings
from app.models.source import SourceRecord
from app.services.nlp_pipeline import nlp_pipeline
from app.services.official_feed_filtering import KeywordMatcher, build_official_feed_keyword_matcher
from app.services.place_gazetteer import place_gazetteer
from app.services.seed_data import REGION_COORDINATES
from app.services.source_registry import source_registry_service


@dataclass(slots=True)
class OfficialFeedAccount:
    source_id: str
    source_name: str
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
    is_custom: bool


@dataclass(slots=True)
class OfficialFeedPost:
    id: str
    source_id: str
    source_name: str
    is_custom: bool
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
    is_safety_relevant: bool
    category: str
    severity: str
    region: str
    location_name: str
    location: dict[str, float]
    risk_score: float
    keywords: list[str]
    matched_keywords: list[str] = field(default_factory=list)
    primary_keyword: str | None = None
    ai_signals: list[str] | None = None
    ai_scenario: str | None = None
    ai_severity: str | None = None
    ai_confidence: float | None = None
    ai_is_rumor: bool | None = None
    ai_sentiment: str | None = None
    location_resolution_method: str = "none"   # "ai" | "fallback" | "none"
    ai_analysis_status: str = "missing_key"    # "success" | "timeout" | "error" | "missing_key"
    ai_location_names: list[str] = field(default_factory=list)  # English gazetteer names for all AI-resolved locations

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

LEBANON_CONTEXT_KEYWORDS: tuple[str, ...] = (
    "lebanon",
    "lebanese",
    "beirut",
    "tripoli",
    "akkar",
    "sidon",
    "saida",
    "tyre",
    "sour",
    "nabatieh",
    "baalbek",
    "hermel",
    "bekaa",
    "zahle",
    "south lebanon",
    "north lebanon",
    "mount lebanon",
    "khiam",
    "marjayoun",
    "bint jbeil",
    "kfar kila",
    "yaroun",
    "houla",
    "naqoura",
    "لبنان",
    "اللبناني",
    "بيروت",
    "طرابلس",
    "عكار",
    "صيدا",
    "صيدا",
    "صور",
    "النبطية",
    "بعلبك",
    "الهرمل",
    "البقاع",
    "زحلة",
    "الجنوب",
    "جنوب لبنان",
    "الشمال",
    "جبل لبنان",
    "الخيام",
    "مرجعيون",
    "بنت جبيل",
    "كفركلا",
    "يارون",
    "حولا",
    "الناقورة",
    "الضاحية",
    "الزهراني",
    "العدوسية",
    "عيتا الشعب",
    "حاصبيا",
)

REGION_KEYWORDS: list[tuple[str, str, str]] = [
    ("beirut", "Beirut", "Beirut"),
    ("بيروت", "Beirut", "Beirut"),
    ("tripoli", "North Lebanon", "Tripoli"),
    ("طرابلس", "North Lebanon", "Tripoli"),
    ("akkar", "Akkar", "Akkar"),
    ("عكار", "Akkar", "Akkar"),
    ("sidon", "South Lebanon", "Sidon"),
    ("saida", "South Lebanon", "Sidon"),
    ("صيدا", "South Lebanon", "Sidon"),
    ("tyre", "South Lebanon", "Tyre"),
    ("sour", "South Lebanon", "Tyre"),
    ("صور", "South Lebanon", "Tyre"),
    ("south lebanon", "South Lebanon", "South Lebanon"),
    ("جنوب لبنان", "South Lebanon", "South Lebanon"),
    ("الجنوب", "South Lebanon", "South Lebanon"),
    ("nabatieh", "Nabatieh", "Nabatieh"),
    ("النبطية", "Nabatieh", "Nabatieh"),
    ("bekaa", "Bekaa", "Bekaa Valley"),
    ("البقاع", "Bekaa", "Bekaa Valley"),
    ("zahle", "Bekaa", "Zahle"),
    ("زحلة", "Bekaa", "Zahle"),
    ("baalbek", "Baalbek-Hermel", "Baalbek"),
    ("بعلبك", "Baalbek-Hermel", "Baalbek"),
    ("hermel", "Baalbek-Hermel", "Hermel"),
    ("الهرمل", "Baalbek-Hermel", "Hermel"),
    ("khiam", "Nabatieh", "Khiam"),
    ("الخيام", "Nabatieh", "Khiam"),
    ("marjayoun", "Nabatieh", "Marjayoun"),
    ("مرجعيون", "Nabatieh", "Marjayoun"),
    ("bint jbeil", "Nabatieh", "Bint Jbeil"),
    ("بنت جبيل", "Nabatieh", "Bint Jbeil"),
    ("kfar kila", "Nabatieh", "Kfar Kila"),
    ("كفركلا", "Nabatieh", "Kfar Kila"),
    ("yaroun", "Nabatieh", "Yaroun"),
    ("يارون", "Nabatieh", "Yaroun"),
    ("houla", "Nabatieh", "Houla"),
    ("حولا", "Nabatieh", "Houla"),
    ("naqoura", "South Lebanon", "Naqoura"),
    ("الناقورة", "South Lebanon", "Naqoura"),
    ("mount lebanon", "Mount Lebanon", "Mount Lebanon"),
    ("جبل لبنان", "Mount Lebanon", "Mount Lebanon"),
    ("lebanon", "Beirut", "Lebanon"),
    ("لبنان", "Beirut", "Lebanon"),
]
AMBIGUOUS_REGION_KEYWORDS: set[str] = {"\u0635\u0648\u0631"}
REGION_LOCATIVE_CONTEXT_TOKENS: set[str] = {
    "in", "at", "near", "to", "from", "city", "town", "village", "area", "district", "suburb",
    "\u0641\u064a", "\u0625\u0644\u0649", "\u0627\u0644\u0649", "\u0645\u0646", "\u0646\u062d\u0648", "\u0642\u0631\u0628", "\u0639\u0644\u0649",
    "\u0645\u062f\u064a\u0646\u0629", "\u0628\u0644\u062f\u0629", "\u0642\u0631\u064a\u0629", "\u0645\u0646\u0637\u0642\u0629", "\u0636\u0627\u062d\u064a\u0629",
}

CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "violence",
        (
            "attack", "attacks", "airstrike", "airstrikes", "strike", "strikes", "raid", "raids",
            "rocket", "rockets", "missile", "missiles", "shooting", "shelling", "clash", "clashes",
            "explosion", "explosions", "bomb", "bombing", "evacuation", "evacuate", "armed", "military",
            "احتلال", "توغل", "غارة", "غارات", "قصف", "استهداف", "صاروخ", "صواريخ", "قذيفة", "قذائف",
            "هجوم", "هجمات", "اشتباك", "اشتباكات", "إطلاق نار", "اطلاق نار", "تفجير", "تفجيرات",
            "انفجار", "انفجارات", "تحذير", "إنذار", "اخلاء", "إخلاء", "اغتيال", "الجيش الإسرائيلي",
            "الجيش الاسرائيلي", "حزب الله", "مسيّرة", "مسيرة", "طائرة مسيرة", "المنطقة العازلة", "تدمير قرى",
        ),
    ),
    (
        "protest",
        (
            "protest", "protests", "demonstration", "demonstrations", "march", "sit-in", "strike action",
            "احتجاج", "احتجاجات", "تظاهرة", "تظاهرات", "اعتصام", "إضراب", "اضراب", "مسيرة",
        ),
    ),
    (
        "natural_disaster",
        (
            "flood", "flooding", "storm", "wildfire", "earthquake", "heavy rain", "snow",
            "فيضان", "فيضانات", "سيول", "عاصفة", "حريق", "حرائق", "زلزال", "أمطار", "امطار", "ثلوج",
        ),
    ),
    (
        "infrastructure",
        (
            "power", "electricity", "outage", "airport", "port", "road", "bridge", "telecom",
            "water station", "water plant", "تحلية المياه", "محطة كهرباء", "محطة القوى", "كهرباء",
            "انقطاع", "طريق", "أوتوستراد", "اوتوستراد", "جسر", "مرفأ", "مطار", "اتصالات", "محطة تحلية",
        ),
    ),
    (
        "health",
        (
            "hospital", "health", "clinic", "ambulance", "emergency room",
            "مستشفى", "مستشفيات", "إسعاف", "اسعاف", "صليب أحمر", "مركز صحي", "طوارئ",
        ),
    ),
    (
        "terrorism",
        (
            "terror", "terrorism", "militant", "device",
            "إرهاب", "ارهاب", "عبوة", "خلية", "انتحاري",
        ),
    ),
    (
        "cyber",
        (
            "cyber", "hack", "breach", "malware", "ransomware",
            "اختراق", "هجوم سيبراني", "قرصنة",
        ),
    ),
]

CRITICAL_KEYWORDS: tuple[str, ...] = (
    "airstrike", "airstrikes", "explosion", "explosions", "bombing", "rocket", "rockets",
    "missile", "missiles", "killed", "dead", "evacuation", "evacuate",
    "غارة", "غارات", "قصف", "استهداف", "صاروخ", "صواريخ", "تفجير", "تفجيرات",
    "انفجار", "انفجارات", "قتيل", "قتلى", "شهيد", "شهداء", "إخلاء", "اخلاء",
)

HIGH_KEYWORDS: tuple[str, ...] = (
    "attack", "attacks", "raid", "clash", "clashes", "shooting", "shelling",
    "outage", "flood", "protest", "hospital", "warning", "alert", "injured", "wounded",
    "هجوم", "هجمات", "اشتباك", "اشتباكات", "إطلاق نار", "اطلاق نار", "حادث", "حادث سير",
    "جرحى", "جريح", "تحذير", "إنذار", "انقطاع", "احتجاج", "إضراب", "اضراب",
)

OFFICIAL_SOURCE_PROFILES: dict[str, dict[str, object]] = {
    "lbci_news": {
        "publisher_name": "LBCI",
        "account_label": "LBCI News Wire",
        "publisher_type": "tv",
        "credibility": "verified",
        "credibility_score": 88.0,
        "initials": "LB",
    },
    "mtvlebanonews": {
        "publisher_name": "MTV Lebanon",
        "account_label": "MTV Lebanon News",
        "publisher_type": "tv",
        "credibility": "high",
        "credibility_score": 84.0,
        "initials": "MT",
    },
    "aljadeedtelegram": {
        "publisher_name": "Al Jadeed",
        "account_label": "Al Jadeed News",
        "publisher_type": "tv",
        "credibility": "high",
        "credibility_score": 82.0,
        "initials": "AJ",
    },
    "almanarnews": {
        "publisher_name": "Al Manar",
        "account_label": "Al Manar TV",
        "publisher_type": "tv",
        "credibility": "high",
        "credibility_score": 80.0,
        "initials": "AM",
    },
}


class OfficialFeedService:
    def __init__(self) -> None:
        self._cache: list[OfficialFeedPost] = []
        self._cached_at: datetime | None = None
        self._cache_ttl = timedelta(minutes=3)
        self._refresh_lock = asyncio.Lock()
        self._is_refreshing = False

    def invalidate_cache(self) -> None:
        self._cache = []
        self._cached_at = None

    async def fetch_posts(self, limit: int | None = None) -> list[OfficialFeedPost]:
        settings = get_settings()
        if not settings.official_feeds_enabled:
            return []

        requested_limit = max(1, min(limit or settings.official_feed_limit, 50))
        now = datetime.now(UTC)

        # Always return from cache immediately — never block the HTTP request
        # on live Telegram scraping. The background loop keeps the cache fresh.
        cache_fresh = self._cached_at and now - self._cached_at < self._cache_ttl
        if cache_fresh:
            return self._cache[:requested_limit]

        # Cache is stale or empty. If no refresh is running, kick one off in the
        # background so the next request (after ~30-60s) gets fresh data.
        if not self._is_refreshing:
            asyncio.ensure_future(self._do_refresh())

        # Return whatever is in cache right now (may be empty on first load).
        return self._cache[:requested_limit]

    async def _do_refresh(self) -> None:
        """Fetch and process posts from all accounts, then update the cache."""
        if self._is_refreshing:
            return
        self._is_refreshing = True
        try:
            settings = get_settings()
            now = datetime.now(UTC)
            cutoff = now - timedelta(hours=48)
            accounts = self._accounts()
            if not accounts:
                return
            keyword_matcher = build_official_feed_keyword_matcher(settings.official_feed_filter_keywords)
            posts: list[OfficialFeedPost] = []
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                headers={"User-Agent": "CrisisShield/1.0 (+local-dev)"},
            ) as client:
                # Fetch all accounts concurrently
                results = await asyncio.gather(
                    *[self._fetch_posts_for_account(client, account, cutoff) for account in accounts],
                    return_exceptions=True,
                )
                for result in results:
                    if isinstance(result, list):
                        posts.extend(result)

            posts.sort(key=lambda item: item.published_at, reverse=True)
            recent_posts = [post for post in posts if post.published_at >= cutoff]
            deduped = self._dedupe_posts(recent_posts)

            # Process posts concurrently (NLP + Claude AI)
            process_results = await asyncio.gather(
                *[self._process_post(post, keyword_matcher) for post in deduped],
                return_exceptions=True,
            )
            filtered = [p for p in process_results if isinstance(p, OfficialFeedPost)]
            filtered.sort(key=lambda item: item.published_at, reverse=True)
            self._cache = filtered
            self._cached_at = now
            logger.info("Official feeds cache refreshed: %d posts from %d accounts", len(filtered), len(accounts))
        except Exception as exc:
            logger.warning("Official feeds refresh failed: %s", exc)
        finally:
            self._is_refreshing = False

    async def start_background_refresh(self) -> None:
        """Start a background loop that refreshes the cache every 3 minutes.
        Call once from app lifespan after startup."""
        # Trigger an immediate first refresh so data is available quickly
        asyncio.ensure_future(self._do_refresh())
        asyncio.ensure_future(self._refresh_loop())

    async def _refresh_loop(self) -> None:
        """Periodic background refresh — runs forever."""
        while True:
            await asyncio.sleep(self._cache_ttl.total_seconds())
            try:
                await self._do_refresh()
            except Exception as exc:
                logger.warning("Official feeds background refresh error: %s", exc)

    async def _fetch_posts_for_account(
        self,
        client: httpx.AsyncClient,
        account: OfficialFeedAccount,
        cutoff: datetime,
    ) -> list[OfficialFeedPost]:
        collected: list[OfficialFeedPost] = []
        seen_post_urls: set[str] = set()
        seen_before_values: set[int] = set()
        next_before: int | None = None

        for _ in range(30):
            page_url = account.feed_url if next_before is None else f"{account.feed_url}?before={next_before}"
            try:
                response = await client.get(page_url)
                response.raise_for_status()
            except httpx.HTTPError:
                break

            page_posts, oldest_message_id = self._parse_telegram_channel_page(account, response.text)
            if not page_posts:
                break

            fresh_posts: list[OfficialFeedPost] = []
            for post in page_posts:
                if post.post_url in seen_post_urls:
                    continue
                seen_post_urls.add(post.post_url)
                fresh_posts.append(post)

            if not fresh_posts:
                break

            collected.extend(fresh_posts)
            oldest_page_timestamp = min(post.published_at for post in fresh_posts)
            if oldest_page_timestamp < cutoff:
                break

            if oldest_message_id is None or oldest_message_id in seen_before_values:
                break

            seen_before_values.add(oldest_message_id)
            next_before = oldest_message_id

        return collected

    def _accounts(self) -> list[OfficialFeedAccount]:
        return [self._account_from_source(source) for source in source_registry_service.list_active_sources("telegram")]

    def _account_from_source(self, source: SourceRecord) -> OfficialFeedAccount:
        profile = OFFICIAL_SOURCE_PROFILES.get(source.username.casefold(), {})
        publisher_name = str(profile.get("publisher_name", source.name)).strip() or source.name
        account_label = str(profile.get("account_label", source.name)).strip() or source.name
        publisher_type = str(profile.get("publisher_type", "social_media")).strip() or "social_media"
        credibility = str(profile.get("credibility", "moderate" if source.is_custom else "high")).strip() or "moderate"
        credibility_score = float(profile.get("credibility_score", 68.0 if source.is_custom else 80.0))
        initials = str(profile.get("initials", self._initials_for_name(source.name))).strip() or "TG"
        handle = source.username.strip().lstrip("@")

        return OfficialFeedAccount(
            source_id=source.id,
            source_name=source.name,
            publisher_name=publisher_name,
            publisher_type=publisher_type,
            credibility=credibility,
            credibility_score=credibility_score,
            initials=initials,
            platform="telegram",
            handle=handle,
            account_label=account_label,
            account_url=f"https://t.me/{handle}",
            feed_url=f"https://t.me/s/{handle}",
            is_custom=source.is_custom,
        )

    def _parse_telegram_channel(self, account: OfficialFeedAccount, html_text: str) -> list[OfficialFeedPost]:
        posts, _ = self._parse_telegram_channel_page(account, html_text)
        return posts

    def _parse_telegram_channel_page(
        self,
        account: OfficialFeedAccount,
        html_text: str,
    ) -> tuple[list[OfficialFeedPost], int | None]:
        posts: list[OfficialFeedPost] = []
        oldest_message_id: int | None = None
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

            if post_match:
                message_id = self._extract_message_id(post_match.group(1))
                if message_id is not None:
                    oldest_message_id = message_id if oldest_message_id is None else min(oldest_message_id, message_id)

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
                    source_id=account.source_id,
                    source_name=account.source_name,
                    is_custom=account.is_custom,
                    platform=account.platform,
                    publisher_name=account.publisher_name,
                    account_label=account.account_label,
                    account_handle=account.handle,
                    account_url=account.account_url,
                    post_url=post_url,
                    content=content,
                    signal_tags=self._extract_tags(content),
                    source_info={
                        "name": account.source_name,
                        "type": account.publisher_type,
                        "credibility": account.credibility,
                        "credibilityScore": account.credibility_score,
                        "logoInitials": account.initials,
                        "url": account.account_url,
                        "verifiedBy": [],
                    },
                    published_at=published_at,
                    is_safety_relevant=False,
                    category="other",
                    severity="medium",
                    region="Beirut",
                    location_name="Lebanon",
                    location={
                        "lat": REGION_COORDINATES["Beirut"][0],
                        "lng": REGION_COORDINATES["Beirut"][1],
                    },
                    risk_score=0.0,
                    keywords=[],
                )
            )

        return posts, oldest_message_id

    async def _process_post(self, post: OfficialFeedPost, keyword_matcher: KeywordMatcher) -> OfficialFeedPost | None:
        from app.services.claude_service import analyze_post

        nlp_result = await nlp_pipeline.process(
            post.content,
            metadata={"source_id": post.source_id, "source_name": post.source_name, "is_custom": post.is_custom},
        )

        # Single unified Claude call — extracts locations AND full analysis in one
        # request (halves API latency vs the former two-call pattern).
        ai_result = await analyze_post(post.content)
        ai_status: str = str(ai_result.get("_status", "error"))
        ai_locations: list[str] = ai_result.get("locations", [])  # type: ignore[assignment]
        ai_location_confidence: float = float(ai_result.get("location_confidence", 0.0))

        enriched = self._enrich_post(
            post,
            nlp_result=nlp_result,
            ai_locations=ai_locations,
            ai_location_confidence=ai_location_confidence,
        )
        if enriched is None:
            return None

        if keyword_matcher.is_enabled:
            match_result = keyword_matcher.match_text(enriched.content)
            if not match_result.has_match:
                return None
            enriched = self._apply_match_metadata(enriched, match_result.matched_keywords)

        # Attach AI intelligence fields — reuse the result already in cache
        enriched = replace(
            enriched,
            ai_signals=ai_result.get("signals", []),
            ai_scenario=ai_result.get("scenario_type"),
            ai_severity=ai_result.get("severity"),
            ai_confidence=ai_result.get("confidence_score"),
            ai_is_rumor=ai_result.get("is_rumor"),
            ai_sentiment=ai_result.get("sentiment"),
            ai_analysis_status=ai_status,
        )

        return enriched

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

    def _extract_message_id(self, post_identifier: str) -> int | None:
        if "/" not in post_identifier:
            return None
        _, raw_id = post_identifier.rsplit("/", 1)
        try:
            return int(raw_id)
        except ValueError:
            return None

    def _extract_tags(self, content: str) -> list[str]:
        lowered = content.lower()
        tags = [tag for tag in KEYWORD_TAGS if tag in lowered]
        for tag in self._extract_hashtags(content):
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

    def _enrich_post(
        self,
        post: OfficialFeedPost,
        *,
        nlp_result: dict[str, object] | None = None,
        ai_locations: list[str] | None = None,
        ai_location_confidence: float = 0.0,
    ) -> OfficialFeedPost | None:
        # Custom sources are added intentionally by the user — always show their posts.
        # Default official sources go through Lebanon relevance + keyword filtering to
        # remove off-topic content from high-volume news channels.
        if not post.is_custom:
            if not self._is_lebanon_relevant(post.content):
                return None

        category = self._infer_category(post.content, nlp_result=nlp_result)
        keywords = self._extract_keywords(post.content, nlp_result=nlp_result)
        # Fall back to hashtags when no category keywords match (common for alert-style
        # channels that use #hashtag + emoji format instead of full sentences).
        if not keywords:
            keywords = self._extract_hashtags(post.content)[:8]
        # For default sources, drop posts with no discernible keywords (likely ads/noise).
        # For custom sources, keep the post even if empty — the user wants to see it.
        if not keywords and not post.is_custom:
            return None

        severity = self._infer_severity(post.content)
        fallback_region, fallback_location_name = self._infer_region(post.content)

        # Location resolution priority:
        #   1. AI-extracted names → gazetteer lookup (exact strings from text, no
        #      false matches like "جديدة" = "new" being treated as Jdeideh).
        #      Only trusted when Claude's location_confidence is ≥ 0.85 — below
        #      that the model was uncertain and we should not surface a label.
        #   2. Raw text gazetteer scan (fallback when AI unavailable or found nothing)
        #   3. Keyword-based region inference (final fallback)
        #
        # Display name strategy:
        #   - Gazetteer exact/alias match → use the clean English name from the DB.
        #   - Gazetteer fuzzy match → DO NOT use it (fuzzy can return a broad nearby
        #     city like "Tyre" for a small village "قصورة").  Instead, display the
        #     exact Arabic string Claude extracted — it IS a literal substring of the
        #     original news text so it is always correct.
        #   - No gazetteer match → display the Arabic name Claude extracted.
        _LOCATION_CONFIDENCE_THRESHOLD = 0.85
        place_match = None
        ai_matched = False
        ai_location_names: list[str] = []
        if ai_locations and ai_location_confidence >= _LOCATION_CONFIDENCE_THRESHOLD:
            for loc in ai_locations:
                if self._is_ambiguous_ai_location_without_context(post.content, loc):
                    continue
                if self._is_probable_partial_ai_location(post.content, loc):
                    continue
                single_match = place_gazetteer.match_candidates([loc])
                if single_match is not None and place_match is None:
                    place_match = single_match  # first match drives the map pin
                    ai_matched = True
                # Decide the display name shown in the blue chip:
                # Only trust the gazetteer's English name for high-confidence matches
                # (exact text substring or known alias).  A "fuzzy" match may resolve
                # "قصورة" → "Tyre" — wrong and confusing.  Show the Arabic name instead.
                if single_match is not None and single_match.match_type in ("exact", "alias"):
                    display_name = single_match.place.name
                else:
                    # Fuzzy or no match: Claude's extracted string is exact from text.
                    display_name = loc
                if display_name not in ai_location_names:
                    ai_location_names.append(display_name)
        location_resolution_method = "ai" if ai_matched else "fallback"

        if place_match is not None:
            region = fallback_region if fallback_region != "Beirut" or fallback_location_name != "Lebanon" else place_match.place.region
            location_name = place_match.place.name
            lat = place_match.place.lat
            lng = place_match.place.lng
        else:
            region, location_name = fallback_region, fallback_location_name
            lat, lng = REGION_COORDINATES.get(region, REGION_COORDINATES["Beirut"])

        return replace(
            post,
            is_safety_relevant=True,
            category=category,
            severity=severity,
            region=region,
            location_name=location_name,
            location={"lat": lat, "lng": lng},
            risk_score=self._risk_score(severity, keywords, nlp_result=nlp_result),
            keywords=keywords,
            signal_tags=self._build_signal_tags(post.content, keywords),
            location_resolution_method=location_resolution_method,
            ai_location_names=ai_location_names,
        )

    def _is_probable_partial_ai_location(self, content: str, candidate: str) -> bool:
        normalized_content = re.sub(r"\s+", " ", content).strip().lower()
        normalized_candidate = re.sub(r"\s+", " ", candidate).strip().lower()
        if not normalized_candidate or " " in normalized_candidate:
            return False

        tokens = normalized_content.split()
        for index, token in enumerate(tokens):
            if token != normalized_candidate:
                continue

            phrases: list[str] = []
            if index > 0:
                phrases.append(f"{tokens[index - 1]} {tokens[index]}")
            if index + 1 < len(tokens):
                phrases.append(f"{tokens[index]} {tokens[index + 1]}")
            if index > 0 and index + 1 < len(tokens):
                phrases.append(f"{tokens[index - 1]} {tokens[index]} {tokens[index + 1]}")

            for phrase in phrases:
                phrase_match = place_gazetteer.match_candidates([phrase])
                if phrase_match is not None and phrase_match.matched_alias != normalized_candidate:
                    return True

        return False

    def _is_ambiguous_ai_location_without_context(self, content: str, candidate: str) -> bool:
        normalized_candidate = re.sub(r"\s+", " ", candidate).strip().lower()
        ambiguous_candidates = {
            "\u0635\u0648\u0631",
            "\u0627\u0644\u0648\u0642\u0641",
            "\u0648\u0627\u0642\u0641",
            "\u0627\u0644\u0648\u0627\u0642\u0641",
        }
        if normalized_candidate not in ambiguous_candidates:
            return False

        normalized_content = re.sub(r"[^\w\u0600-\u06ff]+", " ", content.lower())
        tokens = [token for token in normalized_content.split() if token]
        candidate_tokens = normalized_candidate.split()
        candidate_len = len(candidate_tokens)
        locative_tokens = {
            "in", "at", "near", "to", "from", "city", "town", "village", "area", "district", "suburb",
            "\u0641\u064a", "\u0625\u0644\u0649", "\u0627\u0644\u0649", "\u0645\u0646", "\u0646\u062d\u0648", "\u0642\u0631\u0628", "\u0639\u0644\u0649",
            "\u0645\u062f\u064a\u0646\u0629", "\u0628\u0644\u062f\u0629", "\u0642\u0631\u064a\u0629", "\u0645\u0646\u0637\u0642\u0629", "\u062d\u064a", "\u0636\u0627\u062d\u064a\u0629",
        }

        for start in range(len(tokens) - candidate_len + 1):
            if tokens[start:start + candidate_len] != candidate_tokens:
                continue

            immediate_neighbors = tokens[max(0, start - 1):start] + tokens[start + candidate_len:start + candidate_len + 1]
            if any(token in locative_tokens for token in immediate_neighbors):
                return False

        return True

    def _is_lebanon_relevant(self, content: str) -> bool:
        # Normalise underscores to spaces so hashtag forms like #جنوب_لبنان match
        # the keyword "جنوب لبنان" that uses a space.
        lowered = content.lower().replace("_", " ")
        return any(keyword in lowered for keyword in LEBANON_CONTEXT_KEYWORDS) or place_gazetteer.match_text(content) is not None

    def _infer_region(self, content: str) -> tuple[str, str]:
        lowered = content.lower()
        matches = [
            (keyword, region, location_name)
            for keyword, region, location_name in REGION_KEYWORDS
            if keyword in lowered and (
                keyword not in AMBIGUOUS_REGION_KEYWORDS
                or self._has_region_keyword_context(lowered, keyword)
            )
        ]
        if matches:
            generic_locations = {"Lebanon", "South Lebanon", "North Lebanon", "Mount Lebanon", "Bekaa Valley"}
            _, region, location_name = max(
                matches,
                key=lambda item: (0 if item[2] in generic_locations else 1, len(item[0])),
            )
            return region, location_name
        return "Beirut", "Lebanon"

    def _has_region_keyword_context(self, lowered_content: str, keyword: str) -> bool:
        normalized_content = re.sub(r"[^\w\u0600-\u06ff]+", " ", lowered_content)
        tokens = [token for token in normalized_content.split() if token]
        keyword_tokens = keyword.split()
        keyword_len = len(keyword_tokens)

        for start in range(len(tokens) - keyword_len + 1):
            if tokens[start:start + keyword_len] != keyword_tokens:
                continue

            immediate_neighbors = tokens[max(0, start - 1):start] + tokens[start + keyword_len:start + keyword_len + 1]
            if any(token in REGION_LOCATIVE_CONTEXT_TOKENS for token in immediate_neighbors):
                return True

        return False

    def _infer_category(self, content: str, *, nlp_result: dict[str, object] | None = None) -> str:
        candidate = str((nlp_result or {}).get("category", "")).strip().lower().replace(" ", "_")
        if candidate in {"violence", "protest", "natural_disaster", "infrastructure", "health", "terrorism", "cyber", "other"}:
            return candidate
        lowered = content.lower()
        for category, keywords in CATEGORY_KEYWORDS:
            if any(keyword in lowered for keyword in keywords):
                return category
        return "other"

    def _infer_severity(self, content: str) -> str:
        lowered = content.lower()
        if any(keyword in lowered for keyword in CRITICAL_KEYWORDS):
            return "critical"
        if any(keyword in lowered for keyword in HIGH_KEYWORDS):
            return "high"
        return "medium"

    def _extract_keywords(self, content: str, *, nlp_result: dict[str, object] | None = None) -> list[str]:
        lowered = content.lower()
        keywords: list[str] = []
        for keyword in (nlp_result or {}).get("keywords", []):
            normalized_keyword = str(keyword).strip().lower()
            if normalized_keyword and normalized_keyword not in keywords:
                keywords.append(normalized_keyword)
        for _, category_keywords in CATEGORY_KEYWORDS:
            for keyword in category_keywords:
                if keyword in lowered and keyword not in keywords:
                    keywords.append(keyword)
        return keywords[:8]

    def _build_signal_tags(self, content: str, keywords: list[str], matched_keywords: list[str] | None = None) -> list[str]:
        merged: list[str] = []
        for tag in [*(matched_keywords or []), *self._extract_tags(content), *keywords]:
            if tag not in merged:
                merged.append(tag)
        return merged[:8]

    def _apply_match_metadata(self, post: OfficialFeedPost, matched_keywords: list[str]) -> OfficialFeedPost:
        return replace(
            post,
            matched_keywords=matched_keywords,
            primary_keyword=matched_keywords[0] if matched_keywords else None,
            signal_tags=self._merge_matched_signal_tags(post.signal_tags, matched_keywords, post.content),
        )

    def _apply_keyword_filter(self, posts: list[OfficialFeedPost], matcher: KeywordMatcher) -> list[OfficialFeedPost]:
        if not matcher.is_enabled:
            return posts

        filtered_posts: list[OfficialFeedPost] = []
        for post in posts:
            match_result = matcher.match_text(post.content)
            if not match_result.has_match:
                continue
            filtered_posts.append(self._apply_match_metadata(post, match_result.matched_keywords))
        return filtered_posts

    def _risk_score(self, severity: str, keywords: list[str], *, nlp_result: dict[str, object] | None = None) -> float:
        base = {"medium": 58.0, "high": 76.0, "critical": 90.0}.get(severity, 52.0)
        keyword_score = float((nlp_result or {}).get("keyword_score", 0.0) or 0.0)
        return min(100.0, round(base + len(keywords) * 1.5 + min(keyword_score, 12.0) * 0.35, 1))

    def _initials_for_name(self, value: str) -> str:
        initials = "".join(part[:1].upper() for part in value.split() if part)
        return initials[:2] or "TG"

    def _merge_matched_signal_tags(self, signal_tags: list[str], matched_keywords: list[str], content: str) -> list[str]:
        merged: list[str] = []
        for tag in [*matched_keywords, *signal_tags, *self._extract_hashtags(content)]:
            if tag not in merged:
                merged.append(tag)
        return merged[:8]

    def _extract_hashtags(self, content: str) -> list[str]:
        return [match.group(1).lower() for match in re.finditer(r"#([\w\u0600-\u06ff]+)", content)]


official_feed_service = OfficialFeedService()
