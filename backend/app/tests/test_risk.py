"""Tests for /api/v1/risk endpoints."""
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


# ---------------------------------------------------------------------------
# Current risk scores
# ---------------------------------------------------------------------------

def test_current_risk_returns_list() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/risk/current", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) > 0


def test_current_risk_has_required_fields() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        resp = client.get("/api/v1/risk/current", headers=headers)
    item = resp.json()["data"][0]
    required = ["region", "overall_score", "sentiment_component", "volume_component",
                "keyword_component", "behavior_component", "geospatial_component", "confidence"]
    for field in required:
        assert field in item, f"Missing field: {field}"


def test_risk_scores_are_in_range() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        resp = client.get("/api/v1/risk/current", headers=headers)
    for item in resp.json()["data"]:
        assert 0 <= item["overall_score"] <= 100
        assert 0 <= item["confidence"] <= 1


# ---------------------------------------------------------------------------
# Region detail
# ---------------------------------------------------------------------------

def test_region_detail_beirut() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/risk/region/Beirut", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["region"] == "Beirut"
    assert "overall_score" in data
    assert "is_anomalous" in data
    assert "escalation_probability" in data
    assert "incident_count_24h" in data


def test_region_detail_all_governorates() -> None:
    regions = ["Beirut", "North Lebanon", "South Lebanon", "Mount Lebanon",
               "Bekaa", "Nabatieh", "Akkar", "Baalbek-Hermel"]
    with TestClient(app) as client:
        headers = _auth_headers(client)
        for region in regions:
            resp = client.get(f"/api/v1/risk/region/{region}", headers=headers)
            assert resp.status_code == 200, f"Failed for region: {region}"
            assert resp.json()["data"]["region"] == region


def test_region_detail_unknown_region_404() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/risk/region/NonExistentRegion123", headers=headers)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

def test_predictions_endpoint_returns_list() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/risk/predictions", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)


def test_predictions_horizons_are_valid() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        resp = client.get("/api/v1/risk/predictions", headers=headers)
    valid_horizons = {"24h", "48h", "7d"}
    for item in resp.json()["data"]:
        assert item["horizon"] in valid_horizons
        assert 0 <= item["predicted_score"] <= 100
        assert 0 <= item["confidence"] <= 1


def test_predictions_filter_by_region() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        resp = client.get("/api/v1/risk/predictions?region=Beirut", headers=headers)
    assert resp.status_code == 200
    for item in resp.json()["data"]:
        assert item["region"] == "Beirut"


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def test_risk_history_returns_list() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/risk/history?region=Beirut", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_risk_requires_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/risk/current")
    assert response.status_code in (401, 403)
