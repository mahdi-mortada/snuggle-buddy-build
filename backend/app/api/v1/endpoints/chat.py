from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.services.local_store import local_store

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context: dict[str, Any] = {}


class ChatResponse(BaseModel):
    answer: str
    model: str = "claude-haiku-4-5-20251001"


def _build_system_prompt(live_incidents: list, live_alerts: list, live_risk: list) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    incident_lines = "\n".join(
        f"- [{i.severity.upper()}] {i.title} | Region: {i.region} | Risk: {i.risk_score:.1f} | Source: {i.source_info.get('name', 'unknown') if isinstance(i.source_info, dict) else getattr(i.source_info, 'name', 'unknown')}"
        for i in live_incidents[:15]
    ) or "No incidents currently loaded."

    alert_lines = "\n".join(
        f"- [{a.severity.upper()}] {a.title} | Region: {a.region}"
        for a in live_alerts[:10]
    ) or "No active alerts."

    risk_lines = "\n".join(
        f"- {r.region}: {r.overall_score:.1f}/100"
        for r in sorted(live_risk, key=lambda x: x.overall_score, reverse=True)[:8]
    ) or "No risk scores available."

    return f"""You are CrisisShield AI, a real-time crisis intelligence assistant for Lebanon.
Current date and time: {today}

Your role:
- Answer questions about the LIVE dashboard data shown below — this is real-time data, not historical.
- For incident, alert, and regional risk questions, base your answers ONLY on the live data provided.
- For general Lebanon context questions, use your knowledge but always clarify it is background context.
- Never present your training-data knowledge as current events. Always ground current-event answers in the live data below.
- Be concise, analytical, and practical for a security operations team.

=== LIVE DASHBOARD DATA (as of {today}) ===

CURRENT INCIDENTS (most recent):
{incident_lines}

ACTIVE ALERTS:
{alert_lines}

REGIONAL RISK SCORES (current):
{risk_lines}
=== END LIVE DATA ===

When answering:
- If the user asks about current incidents or alerts, use ONLY the live data above.
- If the live data does not contain what the user asked for, say so clearly.
- Do not invent or guess incident details not present in the live data.
- Format responses in clear markdown with bullet points where helpful."""


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    settings = get_settings()

    if not settings.claude_api_key:
        return ChatResponse(
            answer="The AI chat feature requires a Claude API key. Please set `CLAUDE_API_KEY` in the backend `.env` file.",
            model="none",
        )

    # Fetch live data from local store
    live_incidents = local_store.list_incidents(limit=20)
    live_alerts = local_store.list_alerts(limit=10)
    live_risk = local_store.list_risk_scores()

    system_prompt = _build_system_prompt(live_incidents, live_alerts, live_risk)

    # Build message list for Claude (exclude system, just user/assistant turns)
    claude_messages = [
        {"role": m.role, "content": m.content}
        for m in request.messages
        if m.role in ("user", "assistant")
    ]

    if not claude_messages:
        return ChatResponse(answer="No message provided.", model="none")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.claude_api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=claude_messages,
        )
        answer = response.content[0].text if response.content else "No response generated."
        return ChatResponse(answer=answer)

    except Exception as exc:
        logger.error("Claude chat error: %s", exc)
        return ChatResponse(
            answer=f"The AI assistant encountered an error: {exc}. Please try again.",
            model="error",
        )
