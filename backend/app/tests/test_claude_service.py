from __future__ import annotations

import json
from types import SimpleNamespace

from app.services import claude_service


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.content = [SimpleNamespace(text=text)]


class _FakeMessages:
    def __init__(self, text: str) -> None:
        self._text = text

    async def create(self, **_: object) -> _FakeResponse:
        return _FakeResponse(self._text)


class _FakeAnthropicClient:
    def __init__(self, text: str) -> None:
        self.messages = _FakeMessages(text)


async def test_call_claude_location_keeps_only_exact_substrings(monkeypatch) -> None:
    model_payload = json.dumps(
        {
            "locations": ["عين التينة", "عين الدلب", "العين"],
            "confidence": 0.95,
        },
        ensure_ascii=False,
    )

    monkeypatch.setattr(
        "anthropic.AsyncAnthropic",
        lambda api_key: _FakeAnthropicClient(model_payload),
    )

    result = await claude_service._call_claude_location(  # type: ignore[attr-defined]
        "عين التينة تشهد تحركات سياسية",
        "test-key",
    )

    assert result == {
        "locations": ["عين التينة"],
        "confidence": 0.95,
    }


async def test_analyze_text_returns_fallback_when_key_missing(monkeypatch) -> None:
    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(claude_api_key=""))

    result = await claude_service.analyze_text("No intelligence available")

    assert result == {
        "signals": [],
        "scenario_type": "unclear",
        "severity": "low",
        "confidence_score": 0.0,
        "is_rumor": False,
    }
