from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app
from app.services.official_feeds import OfficialFeedPost, official_feed_service


def _build_post(content: str) -> OfficialFeedPost:
    return OfficialFeedPost(
        id="post-1",
        source_id="source-1",
        source_name="LBCI",
        is_custom=False,
        platform="telegram",
        publisher_name="LBCI",
        account_label="LBCI News Wire",
        account_handle="LBCI_NEWS",
        account_url="https://t.me/LBCI_NEWS",
        post_url="https://t.me/LBCI_NEWS/1",
        content=content,
        signal_tags=["breaking"],
        source_info={
            "name": "LBCI",
            "type": "tv",
            "credibility": "verified",
            "credibilityScore": 88,
            "logoInitials": "LB",
            "url": "https://t.me/LBCI_NEWS",
            "verifiedBy": [],
        },
        published_at=datetime(2026, 3, 31, 8, 0, tzinfo=UTC),
        is_safety_relevant=False,
        category="other",
        severity="medium",
        region="Beirut",
        location_name="Lebanon",
        location={"lat": 33.8938, "lng": 35.5018},
        risk_score=0.0,
        keywords=[],
    )


def test_official_feed_service_enrichs_lebanon_safety_post() -> None:
    post = _build_post("غارة إسرائيلية على بلدة حولا جنوب لبنان وسقوط جرحى")

    enriched = official_feed_service._enrich_post(post)

    assert enriched is not None
    assert enriched.is_safety_relevant is True
    assert enriched.category == "violence"
    assert enriched.severity == "critical"
    assert enriched.region == "Nabatieh"
    assert enriched.location_name == "Hula"
    assert abs(enriched.location["lat"] - 33.2101829) < 0.01
    assert abs(enriched.location["lng"] - 35.5187344) < 0.01
    assert enriched.risk_score >= 90
    assert "غارة" in enriched.keywords
    assert enriched.location_resolution_method == "fallback"  # no ai_locations passed
    assert enriched.ai_analysis_status == "missing_key"       # default since no AI call


def test_official_feed_service_filters_non_safety_post() -> None:
    post = _build_post("وصول رئيس الجمهورية إلى جامعة الروح القدس للمشاركة في رتبة دينية")

    enriched = official_feed_service._enrich_post(post)

    assert enriched is None


def test_official_feeds_endpoint_returns_posts(monkeypatch) -> None:
    async def fake_fetch_posts(limit: int | None = None):
        _ = limit
        enriched = official_feed_service._enrich_post(
            _build_post("غارة إسرائيلية على بلدة حولا جنوب لبنان وسقوط جرحى")
        )
        return [enriched] if enriched is not None else []

    monkeypatch.setattr(official_feed_service, "fetch_posts", fake_fetch_posts)

    with TestClient(app) as client:
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@crisisshield.dev", "password": "admin12345"},
        )
        token = login_response.json()["data"]["access_token"]

        response = client.get(
            "/api/v1/official-feeds",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"][0]["platform"] == "telegram"
    assert payload["data"][0]["source_id"] == "source-1"
    assert payload["data"][0]["is_safety_relevant"] is True
    assert payload["data"][0]["category"] == "violence"
    assert payload["data"][0]["location_name"] == "Hula"


def test_enrich_post_ai_locations_sets_ai_resolution_method() -> None:
    """When AI provides a valid location that matches the gazetteer, method is 'ai'."""
    post = _build_post("غارة على بلدة يارون في الجنوب")
    enriched = official_feed_service._enrich_post(post, ai_locations=["يارون"], ai_location_confidence=0.95)
    assert enriched is not None
    assert enriched.location_resolution_method == "ai"
    assert enriched.location_name == "Yaroun"


def test_enrich_post_empty_ai_locations_sets_fallback_method() -> None:
    """When AI returns no locations, fallback gazetteer/keyword is used and method is 'fallback'."""
    post = _build_post("غارة إسرائيلية على بلدة حولا جنوب لبنان وسقوط جرحى")
    enriched = official_feed_service._enrich_post(post, ai_locations=[])
    assert enriched is not None
    assert enriched.location_resolution_method == "fallback"


def test_official_feeds_endpoint_exposes_resolution_fields(monkeypatch) -> None:
    """API response must include location_resolution_method and ai_analysis_status."""
    async def fake_fetch_posts(limit: int | None = None):
        enriched = official_feed_service._enrich_post(
            _build_post("غارة إسرائيلية على بلدة حولا جنوب لبنان وسقوط جرحى"),
            ai_locations=["حولا"],
            ai_location_confidence=0.95,
        )
        return [enriched] if enriched is not None else []

    monkeypatch.setattr(official_feed_service, "fetch_posts", fake_fetch_posts)

    with TestClient(app) as client:
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@crisisshield.dev", "password": "admin12345"},
        )
        token = login_response.json()["data"]["access_token"]
        response = client.get(
            "/api/v1/official-feeds",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()["data"][0]
    assert data["location_resolution_method"] == "ai"
    assert data["ai_analysis_status"] in ("success", "timeout", "error", "missing_key")


def test_enrich_post_skips_partial_ai_location_token() -> None:
    post = _build_post("غارة في عين التينة")
    enriched = official_feed_service._enrich_post(post, ai_locations=["عين"], ai_location_confidence=0.95)

    assert enriched is not None
    assert enriched.location_resolution_method == "fallback"
    assert enriched.ai_location_names == []


def test_enrich_post_does_not_false_positive_sour_from_photos_text() -> None:
    post = _build_post("نشر الجيش صور الاشتباك على وسائل التواصل")
    enriched = official_feed_service._enrich_post(post, ai_locations=[], ai_location_confidence=0.0)

    assert enriched is not None
    assert enriched.location_resolution_method == "fallback"
    assert enriched.location_name == "Lebanon"
    assert enriched.region == "Beirut"


def test_enrich_post_skips_ambiguous_ai_waqf_without_locative_context() -> None:
    post = _build_post("تحذير أمني في بيروت بشأن الوقف الديني")
    enriched = official_feed_service._enrich_post(post, ai_locations=["الوقف"], ai_location_confidence=0.95)

    assert enriched is not None
    assert enriched.location_resolution_method == "fallback"
    assert enriched.location_name == "Beirut"
    assert enriched.region == "Beirut"
    assert enriched.ai_location_names == []
