from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app
from app.services.official_feeds import OfficialFeedPost, official_feed_service


def test_official_feeds_endpoint_returns_posts(monkeypatch) -> None:
    async def fake_fetch_posts(limit: int | None = None):
        _ = limit
        return [
            OfficialFeedPost(
                id="post-1",
                platform="telegram",
                publisher_name="LBCI",
                account_label="LBCI News Wire",
                account_handle="LBCI_NEWS",
                account_url="https://t.me/LBCI_NEWS",
                post_url="https://t.me/LBCI_NEWS/1",
                content="Breaking update from the official outlet feed.",
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
            )
        ]

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
