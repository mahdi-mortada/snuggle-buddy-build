"""Tests for /api/v1/incidents endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@crisisshield.dev", "password": "admin12345"},
    )
    assert resp.status_code == 200
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# List & pagination
# ---------------------------------------------------------------------------

def test_list_incidents_returns_success() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/incidents", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "items" in payload["data"]


def test_list_incidents_pagination() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        r1 = client.get("/api/v1/incidents?page=1&per_page=5", headers=headers)
        r2 = client.get("/api/v1/incidents?page=2&per_page=5", headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    items1 = r1.json()["data"]["items"]
    items2 = r2.json()["data"]["items"]
    # Pages should not overlap
    ids1 = {i["id"] for i in items1}
    ids2 = {i["id"] for i in items2}
    assert ids1.isdisjoint(ids2), "Page 1 and page 2 should not overlap"


def test_list_incidents_filter_by_region() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/incidents?region=Beirut", headers=headers)
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    for item in items:
        assert item["region"] == "Beirut"


def test_list_incidents_filter_by_severity() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/incidents?severity=critical", headers=headers)
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    for item in items:
        assert item["severity"] == "critical"


def test_list_incidents_filter_by_category() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/incidents?category=violence", headers=headers)
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    for item in items:
        assert item["category"] == "violence"


# ---------------------------------------------------------------------------
# Single incident
# ---------------------------------------------------------------------------

def test_get_incident_by_id() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        list_resp = client.get("/api/v1/incidents?page=1&per_page=1", headers=headers)
        incident_id = list_resp.json()["data"]["items"][0]["id"]
        detail_resp = client.get(f"/api/v1/incidents/{incident_id}", headers=headers)
    assert detail_resp.status_code == 200
    data = detail_resp.json()["data"]
    assert data["id"] == incident_id
    assert "title" in data
    assert "region" in data
    assert "severity" in data


def test_get_incident_not_found() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/incidents/nonexistent-id-xyz", headers=headers)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Live feed
# ---------------------------------------------------------------------------

def test_live_incidents_returns_list() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/incidents/live?limit=10", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) <= 10


# ---------------------------------------------------------------------------
# Geo endpoint
# ---------------------------------------------------------------------------

def test_geo_incidents_returns_geojson() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/incidents/geo", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["type"] == "FeatureCollection"
    assert "features" in data


# ---------------------------------------------------------------------------
# Schema fields
# ---------------------------------------------------------------------------

def test_incident_has_required_fields() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        resp = client.get("/api/v1/incidents?page=1&per_page=1", headers=headers)
    item = resp.json()["data"]["items"][0]
    required = ["id", "title", "description", "category", "severity", "region", "status", "created_at"]
    for field in required:
        assert field in item, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Requires auth
# ---------------------------------------------------------------------------

def test_incidents_require_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/incidents")
    assert response.status_code in (401, 403)
