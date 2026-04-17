import logging
from types import SimpleNamespace

from app.services import telegram_client as telegram_client_module


def test_log_telegram_startup_status_logs_error_when_telethon_missing(monkeypatch, caplog) -> None:
    monkeypatch.setattr(telegram_client_module, "TELETHON_AVAILABLE", False)

    with caplog.at_level(logging.ERROR):
        telegram_client_module.log_telegram_startup_status()

    assert "Telethon is not installed" in caplog.text


def test_log_telegram_startup_status_logs_warning_when_credentials_missing(monkeypatch, caplog) -> None:
    monkeypatch.setattr(telegram_client_module, "TELETHON_AVAILABLE", True)
    monkeypatch.setattr(
        telegram_client_module,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_api_id=0,
            telegram_api_hash="",
            telegram_session_string="",
        ),
    )

    with caplog.at_level(logging.WARNING):
        telegram_client_module.log_telegram_startup_status()

    assert "TELEGRAM_API_ID" in caplog.text
    assert "TELEGRAM_API_HASH" in caplog.text


def test_log_telegram_startup_status_logs_warning_when_session_missing(monkeypatch, caplog) -> None:
    monkeypatch.setattr(telegram_client_module, "TELETHON_AVAILABLE", True)
    monkeypatch.setattr(
        telegram_client_module,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_api_id=123456,
            telegram_api_hash="hash-value",
            telegram_session_string="",
        ),
    )

    with caplog.at_level(logging.WARNING):
        telegram_client_module.log_telegram_startup_status()

    assert "TELEGRAM_SESSION_STRING" in caplog.text
