from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import quote_plus
from uuid import uuid5, NAMESPACE_URL
import re
import xml.etree.ElementTree as ET

import httpx

from app.config import get_settings
from app.models.incident import IncidentLocation, IncidentRecord, SourceInfoRecord
from app.services.local_store import local_store
from app.services.place_gazetteer import place_gazetteer
from app.services.seed_data import REGION_COORDINATES


@dataclass(slots=True)
class NewsEntry:
    title: str
    description: str
    link: str
    source_name: str
    published_at: datetime


SOURCE_PROFILES: dict[str, dict[str, object]] = {
    "reuters": {"name": "Reuters", "type": "news_agency", "credibility": "verified", "score": 95, "initials": "RT"},
    "associated press": {"name": "AP", "type": "news_agency", "credibility": "verified", "score": 94, "initials": "AP"},
    "lbci": {"name": "LBCI", "type": "tv", "credibility": "verified", "score": 88, "initials": "LB"},
    "mtv": {"name": "MTV Lebanon", "type": "tv", "credibility": "high", "score": 84, "initials": "MT"},
    "al jadeed": {"name": "Al Jadeed", "type": "tv", "credibility": "high", "score": 82, "initials": "AJ"},
    "new tv": {"name": "Al Jadeed", "type": "tv", "credibility": "high", "score": 82, "initials": "AJ"},
    "nna": {"name": "NNA", "type": "news_agency", "credibility": "verified", "score": 92, "initials": "NN"},
    "l'orient today": {"name": "L'Orient Today", "type": "newspaper", "credibility": "verified", "score": 90, "initials": "LO"},
    "naharnet": {"name": "Naharnet", "type": "newspaper", "credibility": "high", "score": 80, "initials": "NH"},
    "al jazeera": {"name": "Al Jazeera", "type": "news_agency", "credibility": "high", "score": 86, "initials": "AJ"},
    "al mayadeen": {"name": "Al Mayadeen", "type": "news_agency", "credibility": "high", "score": 80, "initials": "AM"},
    "daily star": {"name": "The Daily Star", "type": "newspaper", "credibility": "high", "score": 80, "initials": "DS"},
}

TRUSTED_SOURCE_KEYS = {
    "reuters",
    "associated press",
    "lbci",
    "mtv",
    "al jadeed",
    "new tv",
    "nna",
    "l'orient today",
    "naharnet",
    "al jazeera",
    "al mayadeen",
    "daily star",
}

LEBANON_RELEVANCE_KEYWORDS = (
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
    "jounieh",
    "baabda",
    "chouf",
    "aley",
    "bekaa",
    "zahle",
    "baalbek",
    "hermel",
    "unifil",
)

NOISE_TITLE_PATTERNS = (
    "leading news destination",
    "subscribe",
    "newsletter",
    "home page",
    "homepage",
)

REGION_KEYWORDS: list[tuple[str, str, str]] = [
    ("beirut", "Beirut", "Beirut"),
    ("tripoli", "North Lebanon", "Tripoli"),
    ("akkar", "Akkar", "Akkar"),
    ("sidon", "South Lebanon", "Sidon"),
    ("saida", "South Lebanon", "Sidon"),
    ("tyre", "South Lebanon", "Tyre"),
    ("sour", "South Lebanon", "Tyre"),
    ("nabatieh", "Nabatieh", "Nabatieh"),
    ("jounieh", "Mount Lebanon", "Jounieh"),
    ("baabda", "Mount Lebanon", "Baabda"),
    ("chouf", "Mount Lebanon", "Chouf"),
    ("aley", "Mount Lebanon", "Aley"),
    ("bekaa", "Bekaa", "Bekaa Valley"),
    ("zahle", "Bekaa", "Zahle"),
    ("baalbek", "Baalbek-Hermel", "Baalbek"),
    ("hermel", "Baalbek-Hermel", "Hermel"),
    ("lebanon", "Beirut", "Lebanon"),
]

CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("violence", ("clash", "attack", "strike", "airstrike", "shelling", "shooting", "killed", "wounded")),
    ("protest", ("protest", "demonstration", "strike action", "sit-in", "march")),
    ("natural_disaster", ("flood", "storm", "wildfire", "earthquake", "rain", "snow")),
    ("infrastructure", ("power", "electricity", "outage", "airport", "port", "road", "telecom", "bridge")),
    ("health", ("hospital", "health", "disease", "cholera", "illness", "clinic")),
    ("terrorism", ("bomb", "explosion", "terror", "militant", "suspicious package")),
    ("cyber", ("cyber", "hack", "breach", "malware", "ransomware")),
]

CRITICAL_KEYWORDS = ("killed", "dead", "airstrike", "explosion", "massive fire", "evacuation", "emergency")
HIGH_KEYWORDS = ("clash", "strike", "raid", "outage", "flood", "protest", "hospital", "crisis")


class LiveNewsService:
    def __init__(self) -> None:
        self._cache: list[IncidentRecord] = []
        self._cached_at: datetime | None = None
        self._cache_ttl = timedelta(minutes=5)

    async def fetch_current_incidents(self, limit: int | None = None) -> list[IncidentRecord]:
        settings = get_settings()
        if not settings.live_news_enabled:
            return []

        requested_limit = limit or settings.live_news_limit
        now = datetime.now(UTC)
        if self._cached_at and now - self._cached_at < self._cache_ttl:
            return self._cache[:requested_limit]

        queries = [
            "(site:reuters.com OR site:apnews.com OR site:lbci.com OR site:nna-leb.gov.lb OR site:today.lorientlejour.com OR site:naharnet.com OR site:mtv.com.lb OR site:aljadeed.tv OR site:aljazeera.net OR site:almayadeen.net) Lebanon when:1d",
            "(site:lbci.com OR site:nna-leb.gov.lb OR site:today.lorientlejour.com OR site:naharnet.com) Beirut OR Lebanon when:1d",
            "(site:reuters.com OR site:apnews.com) Lebanon security OR Lebanon politics OR Lebanon economy when:1d",
            "(site:lbci.com OR site:nna-leb.gov.lb OR site:today.lorientlejour.com OR site:naharnet.com) Lebanon protest OR strike OR outage OR hospital when:1d",
        ]

        entries: list[NewsEntry] = []
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "CrisisShield/1.0 (+local-dev)"},
        ) as client:
            for query in queries:
                feed_url = self._google_news_rss_url(query)
                try:
                    response = await client.get(feed_url)
                    response.raise_for_status()
                except httpx.HTTPError:
                    continue
                entries.extend(self._parse_feed(response.text))

        incidents = self._build_incidents(entries, hours_window=settings.live_news_window_hours)
        self._cache = incidents
        self._cached_at = now
        return incidents[:requested_limit]

    async def sync_current_incidents(self, limit: int | None = None) -> dict[str, int]:
        incidents = await self.fetch_current_incidents(limit=limit)
        inserted, updated = local_store.upsert_incidents(incidents)
        return {
            "fetched": len(incidents),
            "inserted": inserted,
            "updated": updated,
        }

    def _google_news_rss_url(self, query: str) -> str:
        encoded_query = quote_plus(query)
        return f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

    def _parse_feed(self, xml_text: str) -> list[NewsEntry]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        entries: list[NewsEntry] = []
        for item in root.findall(".//item"):
            raw_title = self._clean_text(item.findtext("title"))
            raw_description = self._clean_text(item.findtext("description"))
            link = self._clean_text(item.findtext("link"))
            source_name = self._clean_text(item.findtext("source"))
            published_at = self._parse_date(item.findtext("pubDate"))

            if not raw_title or not link or not published_at:
                continue

            title, source_from_title = self._split_title_source(raw_title)
            final_source = source_name or source_from_title or self._source_from_link(link)
            description = raw_description or title

            entries.append(
                NewsEntry(
                    title=title,
                    description=description,
                    link=link,
                    source_name=final_source or "Google News",
                    published_at=published_at,
                )
            )

        return entries

    def _build_incidents(self, entries: list[NewsEntry], hours_window: int) -> list[IncidentRecord]:
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=hours_window)
        incidents: list[IncidentRecord] = []
        seen_links: set[str] = set()
        seen_titles: set[str] = set()

        for entry in sorted(entries, key=lambda item: item.published_at, reverse=True):
            if entry.published_at < cutoff:
                continue
            clean_title = self._display_title(entry.title)
            if not self._is_relevant_to_lebanon(clean_title, entry.description):
                continue
            if self._is_noise_title(clean_title):
                continue
            trusted_profile = self._trusted_source_profile(entry.source_name, entry.link)
            if not trusted_profile:
                continue

            normalized_title = self._canonical_title(clean_title)
            if entry.link in seen_links or normalized_title in seen_titles:
                continue
            seen_links.add(entry.link)
            seen_titles.add(normalized_title)

            fallback_region, fallback_location_name = self._infer_region(clean_title, entry.description)
            place_match = place_gazetteer.match_text(f"{clean_title}. {entry.description}")
            if place_match is not None:
                region = (
                    fallback_region
                    if fallback_region != "Beirut" or fallback_location_name != "Beirut"
                    else place_match.place.region
                )
                location_name = place_match.place.name
                lat = place_match.place.lat
                lng = place_match.place.lng
            else:
                region, location_name = fallback_region, fallback_location_name
                lat, lng = REGION_COORDINATES[region]
            category = self._infer_category(clean_title, entry.description)
            severity = self._infer_severity(clean_title, entry.description)
            keywords = self._extract_keywords(clean_title, entry.description)
            risk_score = self._risk_score(severity, keywords)
            sentiment_score = self._sentiment_score(clean_title, entry.description)

            incidents.append(
                IncidentRecord(
                    id=f"live-{uuid5(NAMESPACE_URL, entry.link)}",
                    source="news",
                    source_id=entry.link,
                    title=clean_title,
                    description=entry.description,
                    raw_text=f"{clean_title}. {entry.description}",
                    category=category,  # type: ignore[arg-type]
                    severity=severity,  # type: ignore[arg-type]
                    location=IncidentLocation(lat=lat, lng=lng),
                    location_name=location_name,
                    region=region,
                    sentiment_score=sentiment_score,
                    risk_score=risk_score,
                    entities=[location_name, region],
                    keywords=keywords,
                    language="en",
                    status="new",
                    source_info=SourceInfoRecord(
                        name=str(trusted_profile["name"]),
                        type=str(trusted_profile["type"]),  # type: ignore[arg-type]
                        credibility=str(trusted_profile["credibility"]),  # type: ignore[arg-type]
                        credibilityScore=float(trusted_profile["score"]),
                        logoInitials=str(trusted_profile["initials"]),
                        url=entry.link,
                    ),
                    source_url=entry.link,
                    created_at=entry.published_at,
                    updated_at=now,
                )
            )

        return incidents

    def _clean_text(self, value: str | None) -> str:
        if not value:
            return ""
        without_tags = re.sub(r"<[^>]+>", " ", value)
        return re.sub(r"\s+", " ", unescape(without_tags)).strip()

    def _parse_date(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _split_title_source(self, title: str) -> tuple[str, str]:
        if " - " not in title:
            return title, ""
        headline, source = title.rsplit(" - ", 1)
        return headline.strip(), source.strip()

    def _source_from_link(self, link: str) -> str:
        lowered = link.lower()
        for key, profile in SOURCE_PROFILES.items():
            if key.replace(" ", "") in lowered.replace(".", "").replace("-", ""):
                return str(profile["name"])
        return "Google News"

    def _source_profile(self, source_name: str, link: str) -> dict[str, object]:
        lowered = source_name.lower()
        for key, profile in SOURCE_PROFILES.items():
            if key in lowered:
                return profile
        inferred = self._source_from_link(link).lower()
        for key, profile in SOURCE_PROFILES.items():
            if key in inferred:
                return profile
        return {"name": source_name or "Google News", "type": "news_agency", "credibility": "high", "score": 78, "initials": "GN"}

    def _trusted_source_profile(self, source_name: str, link: str) -> dict[str, object] | None:
        lowered = source_name.lower()
        for key, profile in SOURCE_PROFILES.items():
            if key in lowered and key in TRUSTED_SOURCE_KEYS:
                return profile

        inferred_name = self._source_from_link(link).lower()
        for key, profile in SOURCE_PROFILES.items():
            if key in inferred_name and key in TRUSTED_SOURCE_KEYS:
                return profile

        return None

    def _is_relevant_to_lebanon(self, title: str, description: str) -> bool:
        haystack = f"{title} {description}".lower()
        return any(keyword in haystack for keyword in LEBANON_RELEVANCE_KEYWORDS) or place_gazetteer.match_text(haystack) is not None

    def _is_noise_title(self, title: str) -> bool:
        lowered = title.lower()
        return any(pattern in lowered for pattern in NOISE_TITLE_PATTERNS)

    def _canonical_title(self, title: str) -> str:
        return self._normalize_title(self._display_title(title))

    def _display_title(self, title: str) -> str:
        return re.sub(r"^(print|watch|analysis)\s*:\s*", "", title, flags=re.IGNORECASE).strip()

    def _infer_region(self, title: str, description: str) -> tuple[str, str]:
        haystack = f"{title} {description}".lower()
        for keyword, region, location_name in REGION_KEYWORDS:
            if keyword in haystack:
                return region, location_name
        return "Beirut", "Beirut"

    def _infer_category(self, title: str, description: str) -> str:
        haystack = f"{title} {description}".lower()
        for category, keywords in CATEGORY_KEYWORDS:
            if any(keyword in haystack for keyword in keywords):
                return category
        return "other"

    def _infer_severity(self, title: str, description: str) -> str:
        haystack = f"{title} {description}".lower()
        if any(keyword in haystack for keyword in CRITICAL_KEYWORDS):
            return "critical"
        if any(keyword in haystack for keyword in HIGH_KEYWORDS):
            return "high"
        if "warning" in haystack or "concern" in haystack:
            return "medium"
        return "medium"

    def _extract_keywords(self, title: str, description: str) -> list[str]:
        haystack = f"{title} {description}".lower()
        keywords: list[str] = []
        for _, category_keywords in CATEGORY_KEYWORDS:
            for keyword in category_keywords:
                if keyword in haystack and keyword not in keywords:
                    keywords.append(keyword)
        return keywords[:6]

    def _risk_score(self, severity: str, keywords: list[str]) -> float:
        base = {"medium": 58.0, "high": 74.0, "critical": 88.0}.get(severity, 52.0)
        return min(100.0, base + len(keywords) * 2.5)

    def _sentiment_score(self, title: str, description: str) -> float:
        haystack = f"{title} {description}".lower()
        if any(keyword in haystack for keyword in CRITICAL_KEYWORDS):
            return -0.82
        if any(keyword in haystack for keyword in HIGH_KEYWORDS):
            return -0.58
        return -0.25

    def _normalize_title(self, title: str) -> str:
        return re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", title.lower()).strip()


live_news_service = LiveNewsService()
