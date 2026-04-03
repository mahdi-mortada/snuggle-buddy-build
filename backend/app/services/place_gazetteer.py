from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata


PLACES_GEOJSON_PATH = Path(__file__).parents[2] / "data" / "lebanon_places.geojson"
BOUNDARIES_GEOJSON_PATH = Path(__file__).parents[2] / "data" / "lebanon_boundaries.geojson"
LEBANON_BOUNDS = {
    "min_lat": 33.0,
    "max_lat": 34.75,
    "min_lng": 35.0,
    "max_lng": 36.7,
}
PLACE_TYPE_PRIORITY = {
    "city": 5,
    "town": 4,
    "village": 3,
    "hamlet": 2,
    "suburb": 1,
    "neighbourhood": 1,
    "city_block": 0,
}
ALIAS_FIELDS = (
    "name",
    "name:en",
    "name:ar",
    "alt_name",
    "alt_name:ar",
    "long_name",
    "long_name:ar",
    "official_name",
    "official_name:en",
    "official_name:ar",
    "short_name",
)
ARABIC_DIACRITICS_RE = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")


@dataclass(frozen=True, slots=True)
class GazetteerPlace:
    name: str
    name_ar: str | None
    region: str
    district: str | None
    lat: float
    lng: float
    place_type: str
    population: int | None
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GazetteerMatch:
    place: GazetteerPlace
    confidence: float
    matched_alias: str
    match_type: str


class LebanonPlaceGazetteer:
    def __init__(self) -> None:
        self._loaded = False
        self._places: list[GazetteerPlace] = []
        self._alias_index: dict[str, GazetteerPlace] = {}
        self._ranked_aliases: list[tuple[str, GazetteerPlace]] = []
        self._district_features: list[dict[str, object]] = []
        self._governorate_features: list[dict[str, object]] = []

    def match_text(self, text: str) -> GazetteerMatch | None:
        self._ensure_loaded()
        normalized_text = _normalize(text)
        if not normalized_text:
            return None

        haystack = f" {normalized_text} "
        for alias, place in self._ranked_aliases:
            if f" {alias} " not in haystack:
                continue
            confidence = min(0.995, 0.93 + min(len(alias), 32) / 320)
            return GazetteerMatch(
                place=place,
                confidence=round(confidence, 3),
                matched_alias=alias,
                match_type="exact",
            )

        return None

    def match_candidates(self, candidates: list[str]) -> GazetteerMatch | None:
        self._ensure_loaded()

        cleaned = [candidate.strip() for candidate in candidates if candidate and candidate.strip()]
        for candidate in cleaned:
            match = self.match_text(candidate)
            if match is not None:
                return match

        best_match: GazetteerMatch | None = None
        for candidate in cleaned:
            normalized_candidate = _normalize(candidate)
            if not normalized_candidate or len(normalized_candidate) > 64:
                continue

            direct = self._alias_index.get(normalized_candidate)
            if direct is not None:
                return GazetteerMatch(
                    place=direct,
                    confidence=0.98,
                    matched_alias=normalized_candidate,
                    match_type="alias",
                )

            candidate_tokens = normalized_candidate.split()
            if not candidate_tokens:
                continue

            for alias, place in self._ranked_aliases:
                alias_tokens = alias.split()
                if normalized_candidate in alias or alias in normalized_candidate:
                    confidence = 0.87 if normalized_candidate != alias else 0.98
                elif all(token in alias_tokens for token in candidate_tokens):
                    confidence = 0.83
                else:
                    score = _fuzzy_score(normalized_candidate, alias)
                    if score < 0.8:
                        continue
                    confidence = min(0.89, score)

                if best_match is None or confidence > best_match.confidence:
                    best_match = GazetteerMatch(
                        place=place,
                        confidence=round(confidence, 3),
                        matched_alias=alias,
                        match_type="fuzzy",
                    )

        return best_match

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        with PLACES_GEOJSON_PATH.open(encoding="utf-8") as places_file:
            places_geojson = json.load(places_file)
        with BOUNDARIES_GEOJSON_PATH.open(encoding="utf-8") as boundaries_file:
            boundaries_geojson = json.load(boundaries_file)

        self._district_features = [
            feature for feature in boundaries_geojson.get("features", [])
            if (feature.get("properties") or {}).get("type") == "district"
        ]
        self._governorate_features = [
            feature for feature in boundaries_geojson.get("features", [])
            if (feature.get("properties") or {}).get("type") == "governorate"
        ]

        for feature in places_geojson.get("features", []):
            geometry = feature.get("geometry") or {}
            properties = feature.get("properties") or {}
            if geometry.get("type") != "Point":
                continue

            coordinates = geometry.get("coordinates") or []
            if len(coordinates) != 2:
                continue
            lng = float(coordinates[0])
            lat = float(coordinates[1])
            if not _within_lebanon_bounds(lat, lng):
                continue

            aliases = self._extract_aliases(properties)
            if not aliases:
                continue

            governorate = self._locate_feature(lat, lng, self._governorate_features)
            district = self._locate_feature(lat, lng, self._district_features)
            canonical_name = (
                _clean_alias(properties.get("name:en"))
                or _clean_alias(properties.get("name"))
                or _clean_alias(properties.get("name:ar"))
            )
            if not canonical_name or governorate is None:
                continue

            place = GazetteerPlace(
                name=canonical_name,
                name_ar=_clean_alias(properties.get("name:ar")),
                region=str((governorate.get("properties") or {}).get("name") or "Beirut"),
                district=str((district.get("properties") or {}).get("name")) if district is not None else None,
                lat=lat,
                lng=lng,
                place_type=str(properties.get("place") or "village"),
                population=_parse_int(properties.get("population")),
                aliases=tuple(sorted(aliases)),
            )
            self._places.append(place)

            for alias in place.aliases:
                normalized_alias = _normalize(alias)
                if len(normalized_alias) < 3:
                    continue
                existing = self._alias_index.get(normalized_alias)
                if existing is None or self._sort_key(place) > self._sort_key(existing):
                    self._alias_index[normalized_alias] = place

        self._ranked_aliases = sorted(
            self._alias_index.items(),
            key=lambda item: (len(item[0]), self._sort_key(item[1])),
            reverse=True,
        )
        self._loaded = True

    def _extract_aliases(self, properties: dict[str, object]) -> set[str]:
        aliases: set[str] = set()

        for field in ALIAS_FIELDS:
            value = properties.get(field)
            if not isinstance(value, str):
                continue
            for part in re.split(r"[;,/|]", value):
                cleaned = _clean_alias(part)
                if cleaned is not None:
                    aliases.add(cleaned)

        return aliases

    def _locate_feature(self, lat: float, lng: float, features: list[dict[str, object]]) -> dict[str, object] | None:
        for feature in features:
            geometry = feature.get("geometry") or {}
            coordinates = geometry.get("coordinates") or []
            if not coordinates:
                continue
            ring = coordinates[0]
            if _point_in_polygon(lat, lng, ring):
                return feature

        nearest: dict[str, object] | None = None
        nearest_distance = float("inf")
        for feature in features:
            props = feature.get("properties") or {}
            centroid_lat = props.get("centroid_lat")
            centroid_lng = props.get("centroid_lng")
            if centroid_lat is None or centroid_lng is None:
                continue
            distance = _distance(lat, lng, float(centroid_lat), float(centroid_lng))
            if distance < nearest_distance:
                nearest_distance = distance
                nearest = feature
        return nearest

    def _sort_key(self, place: GazetteerPlace) -> tuple[int, int, int]:
        return (
            PLACE_TYPE_PRIORITY.get(place.place_type, 0),
            place.population or 0,
            len(place.aliases),
        )


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.lower().strip())
    text = ARABIC_DIACRITICS_RE.sub("", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"[^0-9a-z\u0600-\u06ff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_alias(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _parse_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _within_lebanon_bounds(lat: float, lng: float) -> bool:
    return (
        LEBANON_BOUNDS["min_lat"] <= lat <= LEBANON_BOUNDS["max_lat"]
        and LEBANON_BOUNDS["min_lng"] <= lng <= LEBANON_BOUNDS["max_lng"]
    )


def _point_in_polygon(lat: float, lng: float, ring: list[list[float]]) -> bool:
    inside = False
    for index, point in enumerate(ring):
        previous = ring[index - 1]
        xi, yi = point
        xj, yj = previous
        intersects = ((yi > lat) != (yj > lat)) and (
            lng < ((xj - xi) * (lat - yi)) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
    return inside


def _distance(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    d_lat = lat_a - lat_b
    d_lng = lng_a - lng_b
    return (d_lat * d_lat + d_lng * d_lng) ** 0.5


def _fuzzy_score(query: str, target: str) -> float:
    if query == target:
        return 1.0
    if query in target or target in query:
        return 0.9

    def bigrams(value: str) -> set[str]:
        return {value[index:index + 2] for index in range(len(value) - 1)} if len(value) >= 2 else {value}

    query_bigrams = bigrams(query)
    target_bigrams = bigrams(target)
    if not query_bigrams or not target_bigrams:
        return 0.0

    overlap = len(query_bigrams & target_bigrams)
    return 2 * overlap / (len(query_bigrams) + len(target_bigrams))


place_gazetteer = LebanonPlaceGazetteer()
