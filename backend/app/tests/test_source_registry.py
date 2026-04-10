from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from app.main import app
from app.services.local_store import local_store
from app.services.official_feeds import official_feed_service
from app.services.source_registry import TelegramValidationResult, source_registry_service
from app.services import source_registry as source_registry_module


def test_normalize_telegram_input_accepts_username_and_link() -> None:
    assert source_registry_service.normalize_telegram_input("@ExampleChannel") == "examplechannel"
    assert source_registry_service.normalize_telegram_input("https://t.me/s/ExampleChannel") == "examplechannel"
    assert source_registry_service.normalize_telegram_input("https://t.me/ExampleChannel") == "examplechannel"
    assert source_registry_service.normalize_telegram_input("Example Channel") == "examplechannel"
    assert source_registry_service.normalize_telegram_input("https://t.me/annaharnewspaper/") == "annaharnewspaper"


def test_sources_endpoint_can_create_toggle_and_delete_source(monkeypatch) -> None:
    original_state = deepcopy(local_store._state)
    original_persist = local_store.persist
    original_validator = source_registry_service.validate_telegram_source
    original_invalidate_cache = official_feed_service.invalidate_cache
    original_log_system_event = source_registry_module.log_system_event
    invalidate_calls: list[str] = []
    log_events: list[tuple[str, str, dict[str, object]]] = []

    async def fake_validate(identifier: str) -> TelegramValidationResult:
        return TelegramValidationResult(name="Custom Watch", username=identifier, telegram_id=987654321)

    monkeypatch.setattr(local_store, "persist", lambda: None)
    monkeypatch.setattr(source_registry_service, "validate_telegram_source", fake_validate)
    monkeypatch.setattr(official_feed_service, "invalidate_cache", lambda: invalidate_calls.append("invalidate"))
    monkeypatch.setattr(source_registry_module, "log_system_event", lambda level, event, details: log_events.append((level, event, details)))

    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/api/v1/auth/login",
                json={"email": "admin@crisisshield.dev", "password": "admin12345"},
            )
            token = login_response.json()["data"]["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            list_response = client.get("/api/v1/official-feeds/sources", headers=headers)
            assert list_response.status_code == 200
            initial_total = len(list_response.json()["data"])

            create_response = client.post(
                "/api/v1/official-feeds/sources",
                headers=headers,
                json={"source_type": "telegram", "name": "CustomWatch", "input": "@CustomWatch"},
            )
            assert create_response.status_code == 201
            created_payload = create_response.json()["data"]
            assert created_payload["name"] == "Custom Watch"
            assert created_payload["username"] == "customwatch"
            assert created_payload["telegram_id"] == 987654321
            assert created_payload["is_custom"] is True

            created_id = created_payload["id"]

            updated_response = client.patch(
                f"/api/v1/official-feeds/sources/{created_id}",
                headers=headers,
                json={"is_active": False},
            )
            assert updated_response.status_code == 200
            assert updated_response.json()["data"]["is_active"] is False

            delete_response = client.delete(
                f"/api/v1/official-feeds/sources/{created_id}",
                headers=headers,
            )
            assert delete_response.status_code == 200
            assert delete_response.json()["data"]["id"] == created_id

            final_list_response = client.get("/api/v1/official-feeds/sources", headers=headers)
            assert final_list_response.status_code == 200
            assert len(final_list_response.json()["data"]) == initial_total

        assert len(invalidate_calls) == 3
        assert (
            "INFO",
            "VALIDATION_START",
            {
                "input_value": "@CustomWatch",
                "extracted_username": "customwatch",
            },
        ) in log_events
        assert (
            "INFO",
            "VALIDATION_SUCCESS",
            {
                "username": "customwatch",
                "telegram_id": 987654321,
            },
        ) in log_events
        assert ("INFO", "SOURCE_ADDED", {
            "name": "Custom Watch",
            "username": "customwatch",
            "telegram_id": 987654321,
            "source_type": "telegram",
            "reason": "created",
        }) in log_events
        assert ("INFO", "SOURCE_DELETED", {
            "username": "customwatch",
            "telegram_id": 987654321,
            "reason": "deleted",
        }) in log_events
    finally:
        local_store._state = original_state
        local_store.persist = original_persist
        source_registry_service.validate_telegram_source = original_validator
        official_feed_service.invalidate_cache = original_invalidate_cache
        source_registry_module.log_system_event = original_log_system_event


def test_sources_endpoint_rejects_duplicates(monkeypatch) -> None:
    original_state = deepcopy(local_store._state)
    original_persist = local_store.persist
    original_validator = source_registry_service.validate_telegram_source
    original_log_system_event = source_registry_module.log_system_event
    log_events: list[tuple[str, str, dict[str, object]]] = []

    async def fake_validate(identifier: str) -> TelegramValidationResult:
        return TelegramValidationResult(name="Duplicate Watch", username=identifier, telegram_id=123456789)

    monkeypatch.setattr(local_store, "persist", lambda: None)
    monkeypatch.setattr(source_registry_service, "validate_telegram_source", fake_validate)
    monkeypatch.setattr(source_registry_module, "log_system_event", lambda level, event, details: log_events.append((level, event, details)))

    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/api/v1/auth/login",
                json={"email": "admin@crisisshield.dev", "password": "admin12345"},
            )
            token = login_response.json()["data"]["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            first_response = client.post(
                "/api/v1/official-feeds/sources",
                headers=headers,
                json={"source_type": "telegram", "input": "@DuplicateWatch"},
            )
            assert first_response.status_code == 201

            duplicate_response = client.post(
                "/api/v1/official-feeds/sources",
                headers=headers,
                json={"source_type": "telegram", "input": "https://t.me/DuplicateWatch"},
            )
            assert duplicate_response.status_code == 400
            assert duplicate_response.json()["detail"] == "Channel already added"
            list_response = client.get("/api/v1/official-feeds/sources", headers=headers)
            duplicate_entries = [source for source in list_response.json()["data"] if source["telegram_id"] == 123456789]
            assert len(duplicate_entries) == 1
            assert (
                "INFO",
                "VALIDATION_START",
                {
                    "input_value": "https://t.me/DuplicateWatch",
                    "extracted_username": "duplicatewatch",
                },
            ) in log_events
            assert (
                "INFO",
                "VALIDATION_SUCCESS",
                {
                    "username": "duplicatewatch",
                    "telegram_id": 123456789,
                },
            ) in log_events
            assert (
                "WARN",
                "DUPLICATE_BLOCKED",
                {
                    "username": "duplicatewatch",
                    "telegram_id": 123456789,
                    "reason": "active_telegram_id",
                },
            ) in log_events
            assert (
                "WARN",
                "SOURCE_ADD_FAILED",
                {
                    "input_value": "https://t.me/DuplicateWatch",
                    "username": "duplicatewatch",
                    "telegram_id": 123456789,
                    "reason": "duplicate",
                },
            ) in log_events
    finally:
        local_store._state = original_state
        local_store.persist = original_persist
        source_registry_service.validate_telegram_source = original_validator
        source_registry_module.log_system_event = original_log_system_event


def test_sources_endpoint_reactivates_inactive_source(monkeypatch) -> None:
    original_state = deepcopy(local_store._state)
    original_persist = local_store.persist
    original_validator = source_registry_service.validate_telegram_source
    original_invalidate_cache = official_feed_service.invalidate_cache
    original_log_system_event = source_registry_module.log_system_event
    invalidate_calls: list[str] = []
    log_events: list[tuple[str, str, dict[str, object]]] = []

    async def fake_validate(identifier: str) -> TelegramValidationResult:
        return TelegramValidationResult(name="Watch Live", username=identifier, telegram_id=555001111)

    monkeypatch.setattr(local_store, "persist", lambda: None)
    monkeypatch.setattr(source_registry_service, "validate_telegram_source", fake_validate)
    monkeypatch.setattr(official_feed_service, "invalidate_cache", lambda: invalidate_calls.append("invalidate"))
    monkeypatch.setattr(source_registry_module, "log_system_event", lambda level, event, details: log_events.append((level, event, details)))

    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/api/v1/auth/login",
                json={"email": "admin@crisisshield.dev", "password": "admin12345"},
            )
            token = login_response.json()["data"]["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            create_response = client.post(
                "/api/v1/official-feeds/sources",
                headers=headers,
                json={"source_type": "telegram", "input": "@WatchLive"},
            )
            assert create_response.status_code == 201
            source_id = create_response.json()["data"]["id"]

            disable_response = client.patch(
                f"/api/v1/official-feeds/sources/{source_id}",
                headers=headers,
                json={"is_active": False},
            )
            assert disable_response.status_code == 200
            assert disable_response.json()["data"]["is_active"] is False

            readd_response = client.post(
                "/api/v1/official-feeds/sources",
                headers=headers,
                json={"source_type": "telegram", "input": "https://t.me/WatchLive/"},
            )
            assert readd_response.status_code == 201
            reactivated_payload = readd_response.json()["data"]
            assert reactivated_payload["id"] == source_id
            assert reactivated_payload["is_active"] is True
            assert reactivated_payload["telegram_id"] == 555001111

            list_response = client.get("/api/v1/official-feeds/sources", headers=headers)
            matching_sources = [source for source in list_response.json()["data"] if source["telegram_id"] == 555001111]
            assert len(matching_sources) == 1
            assert matching_sources[0]["is_active"] is True

        assert len(invalidate_calls) == 3
        assert ("INFO", "SOURCE_ADDED", {
            "name": "Watch Live",
            "username": "watchlive",
            "telegram_id": 555001111,
            "source_type": "telegram",
            "reason": "reactivated",
        }) in log_events
    finally:
        local_store._state = original_state
        local_store.persist = original_persist
        source_registry_service.validate_telegram_source = original_validator
        official_feed_service.invalidate_cache = original_invalidate_cache
        source_registry_module.log_system_event = original_log_system_event
