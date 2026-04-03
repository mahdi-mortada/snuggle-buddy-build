"""Location resolution engine used by ingestion and manual incident flows."""

from __future__ import annotations

import logging
import unicodedata
from typing import Optional

from app.services.place_gazetteer import place_gazetteer

logger = logging.getLogger(__name__)

# Lowercase alias -> canonical region/district name.
REGION_ALIASES: dict[str, str] = {
    # Beirut
    "beirut": "Beirut",
    "beyrouth": "Beirut",
    "بيروت": "Beirut",
    # Mount Lebanon
    "mount lebanon": "Mount Lebanon",
    "jabal lubnan": "Mount Lebanon",
    "جبل لبنان": "Mount Lebanon",
    "metn": "Metn",
    "المتن": "Metn",
    "keserwan": "Keserwan",
    "kesrouane": "Keserwan",
    "كسروان": "Keserwan",
    "chouf": "Chouf",
    "الشوف": "Chouf",
    "aley": "Aley",
    "عاليه": "Aley",
    "baabda": "Baabda",
    "بعبدا": "Baabda",
    "jbeil": "Jbeil (Byblos)",
    "byblos": "Jbeil (Byblos)",
    "جبيل": "Jbeil (Byblos)",
    # North Lebanon
    "north lebanon": "North Lebanon",
    "north": "North Lebanon",
    "الشمال": "North Lebanon",
    "tripoli": "Tripoli",
    "طرابلس": "Tripoli",
    "zgharta": "Zgharta",
    "زغرتا": "Zgharta",
    "koura": "Koura",
    "الكورة": "Koura",
    "bcharre": "Bcharre",
    "bsharri": "Bcharre",
    "بشري": "Bcharre",
    "minieh": "Minieh-Danniyeh",
    "danniyeh": "Minieh-Danniyeh",
    "المنية": "Minieh-Danniyeh",
    # South Lebanon
    "south lebanon": "South Lebanon",
    "south": "South Lebanon",
    "الجنوب": "South Lebanon",
    "sidon": "Sidon",
    "saida": "Sidon",
    "صيدا": "Sidon",
    "صيدون": "Sidon",
    "tyre": "Tyre",
    "sur": "Tyre",
    "صور": "Tyre",
    "jezzine": "Jezzine",
    "جزين": "Jezzine",
    # Nabatieh
    "nabatieh": "Nabatieh",
    "النبطية": "Nabatieh",
    "hasbaya": "Hasbaya",
    "حاصبيا": "Hasbaya",
    "marjayoun": "Marjayoun",
    "مرجعيون": "Marjayoun",
    "bint jbeil": "Bint Jbeil",
    "bint jbail": "Bint Jbeil",
    "بنت جبيل": "Bint Jbeil",
    # Bekaa
    "bekaa": "Bekaa",
    "beqaa": "Bekaa",
    "البقاع": "Bekaa",
    "zahleh": "Zahleh",
    "zahle": "Zahleh",
    "زحلة": "Zahleh",
    "west bekaa": "West Bekaa",
    "البقاع الغربي": "West Bekaa",
    "rachaya": "Rachaya",
    "rashaya": "Rachaya",
    "راشيا": "Rachaya",
    # Baalbek-Hermel
    "baalbek": "Baalbek",
    "baalbeck": "Baalbek",
    "بعلبك": "Baalbek",
    "hermel": "Hermel",
    "الهرمل": "Hermel",
    "baalbek-hermel": "Baalbek-Hermel",
    "بعلبك الهرمل": "Baalbek-Hermel",
    # Akkar
    "akkar": "Akkar",
    "عكار": "Akkar",
}

VALID_REGIONS = sorted(set(REGION_ALIASES.values()))


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = "".join(
        char for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn" or ord(char) < 0x0600
    )
    return " ".join(text.split())


def _fuzzy_score(query: str, target: str) -> float:
    q = _normalize(query)
    t = _normalize(target)
    if q == t:
        return 1.0
    if q in t or t in q:
        return 0.9

    def bigrams(value: str) -> set[str]:
        return {value[index:index + 2] for index in range(len(value) - 1)} if len(value) >= 2 else {value}

    q_bigrams = bigrams(q)
    t_bigrams = bigrams(t)
    if not q_bigrams or not t_bigrams:
        return 0.0

    overlap = len(q_bigrams & t_bigrams)
    return 2 * overlap / (len(q_bigrams) + len(t_bigrams))


async def resolve_location(
    gps_lat: Optional[float] = None,
    gps_lng: Optional[float] = None,
    text_location: Optional[str] = None,
    nlp_gpe_entities: Optional[list[str]] = None,
) -> dict[str, object]:
    """Resolve GPS/text input to a Lebanon region and optional precise place."""
    if gps_lat is not None and gps_lng is not None:
        region = await _resolve_by_gps(gps_lat, gps_lng)
        if region:
            return {"region": region, "confidence": 0.98, "method": "gps"}

    candidates: list[str] = []
    if nlp_gpe_entities:
        candidates.extend(nlp_gpe_entities)
    if text_location:
        candidates.append(text_location)

    place_match = place_gazetteer.match_candidates(candidates)
    if place_match is not None:
        return {
            "region": place_match.place.region,
            "confidence": place_match.confidence,
            "method": "gazetteer",
            "location_name": place_match.place.name,
            "lat": place_match.place.lat,
            "lng": place_match.place.lng,
        }

    best_region, best_score = _resolve_by_text(candidates)
    if best_score >= 0.7:
        return {"region": best_region, "confidence": round(best_score, 3), "method": "nlp"}

    return {"region": "unknown", "confidence": 0.0, "method": "fallback"}


async def _resolve_by_gps(lat: float, lng: float) -> Optional[str]:
    """Query PostGIS to find which district contains the GPS point."""
    from app.db.postgres import postgres_client

    if not postgres_client.is_connected:
        return None

    try:
        from sqlalchemy import text

        async with postgres_client.session_scope() as session:
            result = await session.execute(
                text(
                    """
                    SELECT name FROM regions
                    WHERE type = 'district'
                      AND ST_Within(
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geometry,
                        geom
                      )
                    LIMIT 1
                    """
                ),
                {"lat": lat, "lng": lng},
            )
            row = result.fetchone()
            if row:
                return row[0]

            result2 = await session.execute(
                text(
                    """
                    SELECT name,
                           ST_Distance(
                             ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                             centroid
                           ) AS dist
                    FROM regions
                    WHERE type = 'district'
                    ORDER BY dist
                    LIMIT 1
                    """
                ),
                {"lat": lat, "lng": lng},
            )
            row2 = result2.fetchone()
            if row2:
                return row2[0]
    except Exception as exc:
        logger.warning("GPS region lookup failed: %s", exc)
    return None


def _resolve_by_text(candidates: list[str]) -> tuple[str, float]:
    best_region = "unknown"
    best_score = 0.0

    for candidate in candidates:
        if not candidate:
            continue

        normalized = _normalize(candidate)
        if normalized in REGION_ALIASES:
            return REGION_ALIASES[normalized], 0.95

        for alias, canonical in REGION_ALIASES.items():
            if alias in normalized or normalized in alias:
                score = len(min(alias, normalized, key=len)) / len(max(alias, normalized, key=len))
                if score > best_score:
                    best_score = score * 0.9
                    best_region = canonical

        for region in VALID_REGIONS:
            score = _fuzzy_score(candidate, region)
            if score > best_score:
                best_score = score
                best_region = region

    return best_region, best_score


def get_valid_regions() -> list[str]:
    return VALID_REGIONS
