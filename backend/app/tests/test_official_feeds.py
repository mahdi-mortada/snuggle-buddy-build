from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app
from app.services.official_feeds import OfficialFeedPost, official_feed_service


def _build_post(content: str) -> OfficialFeedPost:
    return OfficialFeedPost(
        id="post-1",
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
    assert payload["data"][0]["is_safety_relevant"] is True
    assert payload["data"][0]["category"] == "violence"
    assert payload["data"][0]["location_name"] == "Hula"
