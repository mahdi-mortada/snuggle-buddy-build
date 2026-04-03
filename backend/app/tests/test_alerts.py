"""Tests for /api/v1/alerts endpoints."""
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
# List alerts
# ---------------------------------------------------------------------------

def test_list_alerts_returns_success() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/alerts", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["data"], list)


def test_alerts_have_required_fields() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        resp = client.get("/api/v1/alerts", headers=headers)
    alerts = resp.json()["data"]
    if not alerts:
        return  # no alerts to check
    required = ["id", "alert_type", "severity", "title", "message", "region",
                "is_acknowledged", "created_at", "linked_incidents"]
    for field in required:
        assert field in alerts[0], f"Missing field: {field}"


def test_alerts_severity_values_valid() -> None:
    valid = {"info", "warning", "critical", "emergency"}
    with TestClient(app) as client:
        headers = _auth_headers(client)
        resp = client.get("/api/v1/alerts", headers=headers)
    for alert in resp.json()["data"]:
        assert alert["severity"] in valid


# ---------------------------------------------------------------------------
# Filter by severity
# ---------------------------------------------------------------------------

def test_filter_alerts_by_severity() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        resp = client.get("/api/v1/alerts?severity=critical", headers=headers)
    for alert in resp.json()["data"]:
        assert alert["severity"] == "critical"


def test_filter_alerts_by_region() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        resp = client.get("/api/v1/alerts?region=Beirut", headers=headers)
    for alert in resp.json()["data"]:
        assert alert["region"] == "Beirut"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_alert_stats_endpoint() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/v1/alerts/stats", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "total" in data
    assert "acknowledged" in data
    assert "by_severity" in data
    assert "average_response_minutes" in data
    assert data["total"] >= 0
    assert data["acknowledged"] >= 0


# ---------------------------------------------------------------------------
# Acknowledge
# ---------------------------------------------------------------------------

def test_acknowledge_alert() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        # Get an unacknowledged alert
        list_resp = client.get("/api/v1/alerts", headers=headers)
        alerts = list_resp.json()["data"]
        unacked = [a for a in alerts if not a["is_acknowledged"]]
        if not unacked:
            return  # nothing to test

        alert_id = unacked[0]["id"]
        ack_resp = client.patch(
            f"/api/v1/alerts/{alert_id}/acknowledge",
            headers=headers,
        )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["data"]["is_acknowledged"] is True


def test_acknowledge_nonexistent_alert_404() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.patch("/api/v1/alerts/nonexistent-alert-xyz/acknowledge", headers=headers)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_alerts_require_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/alerts")
    assert response.status_code in (401, 403)
