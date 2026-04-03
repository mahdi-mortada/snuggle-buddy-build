from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json

DEFAULT_OFFICIAL_FEED_TEXT_FIELDS: tuple[str, ...] = (
    "title",
    "description",
    "content",
    "message",
    "summary",
)


@dataclass(slots=True)
class KeywordMatchResult:
    matched_keywords: list[str]
    primary_keyword: str | None

    @property
    def has_match(self) -> bool:
        return bool(self.matched_keywords)


class KeywordMatcher:
    def __init__(
        self,
        keywords: Sequence[str],
        *,
        text_fields: Sequence[str] = DEFAULT_OFFICIAL_FEED_TEXT_FIELDS,
    ) -> None:
        self._keywords = tuple(_normalize_keywords(keywords))
        self._text_fields = tuple(field.strip() for field in text_fields if field and field.strip())

    @property
    def keywords(self) -> tuple[str, ...]:
        return self._keywords

    @property
    def is_enabled(self) -> bool:
        return bool(self._keywords)

    def match_text(self, text: str) -> KeywordMatchResult:
        normalized_text = _normalize_text(text)
        if not normalized_text or not self._keywords:
            return KeywordMatchResult(matched_keywords=[], primary_keyword=None)

        # A single lowercase pass keeps matching fast for large streams.
        matched_keywords = [keyword for keyword in self._keywords if keyword in normalized_text]
        return KeywordMatchResult(
            matched_keywords=matched_keywords,
            primary_keyword=matched_keywords[0] if matched_keywords else None,
        )

    def match_record(self, record: Mapping[str, object] | object) -> KeywordMatchResult:
        searchable_text = self.build_search_text(record)
        return self.match_text(searchable_text)

    def build_search_text(self, record: Mapping[str, object] | object) -> str:
        parts: list[str] = []
        for field_name in self._text_fields:
            value = record.get(field_name) if isinstance(record, Mapping) else getattr(record, field_name, None)
            text = _coerce_text(value)
            if text:
                parts.append(text)
        return "\n".join(parts)


def build_official_feed_keyword_matcher(raw_keywords: str | None) -> KeywordMatcher:
    return KeywordMatcher(resolve_official_feed_filter_keywords(raw_keywords))


def resolve_official_feed_filter_keywords(raw_keywords: str | None) -> list[str]:
    # A blank config keeps the legacy behavior: return recent posts without
    # suppressing them. Filtering becomes active only when keywords are defined.
    if raw_keywords is None or not raw_keywords.strip():
        return []

    parsed_keywords = _parse_keyword_config(raw_keywords.strip())
    if parsed_keywords is None:
        return []

    normalized_keywords = _normalize_keywords(parsed_keywords)
    return normalized_keywords


def _parse_keyword_config(raw_keywords: str) -> list[str] | None:
    # JSON arrays are the preferred format, but comma-separated values are
    # also accepted to make shell-based updates simpler.
    if raw_keywords.startswith("["):
        try:
            parsed = json.loads(raw_keywords)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        return None

    return [item.strip() for item in raw_keywords.split(",")]


def _normalize_keywords(keywords: Sequence[str]) -> list[str]:
    normalized_keywords: list[str] = []
    seen_keywords: set[str] = set()

    for keyword in keywords:
        normalized_keyword = _normalize_text(keyword)
        if not normalized_keyword or normalized_keyword in seen_keywords:
            continue
        seen_keywords.add(normalized_keyword)
        normalized_keywords.append(normalized_keyword)

    return normalized_keywords


def _coerce_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return " ".join(str(item).strip() for item in value if str(item).strip())
    return ""


def _normalize_text(value: object) -> str:
    return str(value).casefold().strip() if value is not None else ""
