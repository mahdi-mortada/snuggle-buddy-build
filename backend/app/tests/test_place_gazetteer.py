import asyncio

from app.services.location_resolver import resolve_location
from app.services.place_gazetteer import place_gazetteer


def test_place_gazetteer_matches_english_name() -> None:
    match = place_gazetteer.match_text("Security incident reported near Jounieh port.")

    assert match is not None
    assert match.place.name == "Jounieh"
    assert match.place.region == "Mount Lebanon"
    assert abs(match.place.lat - 33.9741506) < 0.01
    assert abs(match.place.lng - 35.6200633) < 0.01


def test_place_gazetteer_matches_arabic_name() -> None:
    match = place_gazetteer.match_text("غارة قرب حولا بعد تحذير أمني.")

    assert match is not None
    assert match.place.name == "Hula"
    assert match.place.region == "South Lebanon"


def test_place_gazetteer_deduplicates_aliases_to_same_place() -> None:
    first = place_gazetteer.match_candidates(["Kfar Kila"])
    second = place_gazetteer.match_candidates(["Kafr Kila"])

    assert first is not None
    assert second is not None
    assert first.place.name == second.place.name == "Kafr Kila"
    assert first.place.lat == second.place.lat
    assert first.place.lng == second.place.lng


def test_resolve_location_uses_gazetteer_before_region_fallback() -> None:
    resolution = asyncio.run(resolve_location(text_location="Jounieh"))

    assert resolution["method"] == "gazetteer"
    assert resolution["region"] == "Mount Lebanon"
    assert resolution["location_name"] == "Jounieh"
