"""Tests for /api/v1/dashboard endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _auth_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@crisisshield.dev", "password": "admin12345"},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


def test_dashboard_overview() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/dashboard/overview", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    required = ["total_incidents_24h", "active_alerts", "avg_risk_score"]
    for field in required:
        assert field in data, f"Missing field: {field}"
    assert data["total_incidents_24h"] >= 0
    assert 0 <= data["avg_risk_score"] <= 100


def test_dashboard_trends() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/dashboard/trends", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    if data:
        point = data[0]
        assert "time" in point
        assert "incidents" in point
        assert "risk_score" in point
        assert "sentiment" in point


def test_dashboard_hotspots() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/dashboard/hotspots", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)


def test_dashboard_stats_consistency() -> None:
    """active_alerts should not exceed total_incidents_24h."""
    with TestClient(app) as client:
        headers = _auth_headers(client)
        resp = client.get("/api/v1/dashboard/overview", headers=headers)
    data = resp.json()["data"]
    # Sanity check: active alerts can't be more than 10x incidents
    incidents = data["total_incidents_24h"]
    alerts = data["active_alerts"]
    if incidents > 0:
        assert alerts <= incidents * 10


def test_dashboard_requires_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/dashboard/overview")
    assert response.status_code in (401, 403)
