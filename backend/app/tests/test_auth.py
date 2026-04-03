from fastapi.testclient import TestClient

from app.main import app


def test_login_and_fetch_profile() -> None:
    with TestClient(app) as client:
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@crisisshield.dev", "password": "admin12345"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["data"]["access_token"]

        profile_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert profile_response.status_code == 200
    payload = profile_response.json()
    assert payload["success"] is True
    assert payload["data"]["email"] == "admin@crisisshield.dev"
