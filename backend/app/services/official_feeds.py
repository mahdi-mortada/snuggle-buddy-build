from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from html import unescape
import json
import re
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

import httpx

from app.config import get_settings
from app.services.place_gazetteer import place_gazetteer
from app.services.seed_data import REGION_COORDINATES


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
    is_safety_relevant: bool
    category: str
    severity: str
    region: str
    location_name: str
    location: dict[str, float]
    risk_score: float
    keywords: list[str]


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


class OfficialFeedService:
    def __init__(self) -> None:
        self._cache: list[OfficialFeedPost] = []
        self._cached_at: datetime | None = None
        self._cache_ttl = timedelta(minutes=3)

    async def fetch_posts(self, limit: int | None = None) -> list[OfficialFeedPost]:
        settings = get_settings()
        if not settings.official_feeds_enabled:
            return []

        requested_limit = limit or settings.official_feed_limit
        now = datetime.now(UTC)
        if self._cached_at and now - self._cached_at < self._cache_ttl:
            return self._cache[:requested_limit]

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
        filtered = [enriched for post in deduped if (enriched := self._enrich_post(post))]
        self._cache = filtered
        self._cached_at = now
        return filtered[:requested_limit]

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

    def _enrich_post(self, post: OfficialFeedPost) -> OfficialFeedPost | None:
        if not self._is_lebanon_relevant(post.content):
            return None

        category = self._infer_category(post.content)
        keywords = self._extract_keywords(post.content)
        if not keywords:
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
            risk_score=self._risk_score(severity, keywords),
            keywords=keywords,
            signal_tags=self._merge_signal_tags(post.signal_tags, keywords),
        )

    def _is_lebanon_relevant(self, content: str) -> bool:
        lowered = content.lower()
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

    def _infer_category(self, content: str) -> str:
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

    def _extract_keywords(self, content: str) -> list[str]:
        lowered = content.lower()
        keywords: list[str] = []
        for _, category_keywords in CATEGORY_KEYWORDS:
            for keyword in category_keywords:
                if keyword in lowered and keyword not in keywords:
                    keywords.append(keyword)
        return keywords[:8]

    def _merge_signal_tags(self, signal_tags: list[str], keywords: list[str]) -> list[str]:
        merged: list[str] = []
        for tag in [*signal_tags, *keywords]:
            if tag not in merged:
                merged.append(tag)
        return merged[:8]

    def _risk_score(self, severity: str, keywords: list[str]) -> float:
        base = {"medium": 58.0, "high": 76.0, "critical": 90.0}.get(severity, 52.0)
        return min(100.0, round(base + len(keywords) * 1.5, 1))


official_feed_service = OfficialFeedService()
