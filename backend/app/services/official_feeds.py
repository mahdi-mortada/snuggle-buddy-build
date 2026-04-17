from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from html import unescape
import re
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

import httpx

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

    def invalidate_cache(self) -> None:
        self._cache = []
        self._cached_at = None

    async def fetch_posts(self, limit: int | None = None) -> list[OfficialFeedPost]:
        settings = get_settings()
        if not settings.official_feeds_enabled:
            return []

        requested_limit = limit or settings.official_feed_limit
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=48)
        if self._cached_at and now - self._cached_at < self._cache_ttl:
            return self._cache[:requested_limit]

        posts: list[OfficialFeedPost] = []
        accounts = self._accounts()
        keyword_matcher = build_official_feed_keyword_matcher(settings.official_feed_filter_keywords)
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "CrisisShield/1.0 (+local-dev)"},
        ) as client:
            for account in accounts:
                posts.extend(await self._fetch_posts_for_account(client, account, cutoff))

        posts.sort(key=lambda item: item.published_at, reverse=True)
        recent_posts = [post for post in posts if post.published_at >= cutoff]
        deduped = self._dedupe_posts(recent_posts)
        filtered: list[OfficialFeedPost] = []
        for post in deduped:
            if enriched := await self._process_post(post, keyword_matcher):
                filtered.append(enriched)
        filtered.sort(key=lambda item: item.published_at, reverse=True)
        self._cache = filtered
        self._cached_at = now
        return filtered[:requested_limit]

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
        nlp_result = await nlp_pipeline.process(
            post.content,
            metadata={"source_id": post.source_id, "source_name": post.source_name, "is_custom": post.is_custom},
        )
        enriched = self._enrich_post(post, nlp_result=nlp_result)
        if enriched is None:
            return None

        if keyword_matcher.is_enabled:
            match_result = keyword_matcher.match_text(enriched.content)
            if not match_result.has_match:
                return None
            enriched = self._apply_match_metadata(enriched, match_result.matched_keywords)

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

    def _enrich_post(self, post: OfficialFeedPost, *, nlp_result: dict[str, object] | None = None) -> OfficialFeedPost | None:
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
        place_match = place_gazetteer.match_text(post.content)
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
        )

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
            if keyword in lowered
        ]
        if matches:
            generic_locations = {"Lebanon", "South Lebanon", "North Lebanon", "Mount Lebanon", "Bekaa Valley"}
            _, region, location_name = max(
                matches,
                key=lambda item: (0 if item[2] in generic_locations else 1, len(item[0])),
            )
            return region, location_name
        return "Beirut", "Lebanon"

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
