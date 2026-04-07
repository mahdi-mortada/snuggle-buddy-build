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


def _fmt_incident_from_dict(i: dict) -> str:
    """Format a camelCase incident dict (from frontend context)."""
    severity = (i.get("severity") or "unknown").upper()
    title = i.get("title") or "Untitled"
    region = i.get("region") or "Unknown"
    risk = i.get("riskScore") or i.get("risk_score") or 0
    source_info = i.get("sourceInfo") or i.get("source_info") or {}
    source = source_info.get("name") if isinstance(source_info, dict) else "Unknown"
    created_at = i.get("createdAt") or i.get("created_at") or ""
    ts = ""
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            ts = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            ts = str(created_at)[:19]
    return f"- [{severity}] {title} | Region: {region} | Risk: {float(risk):.1f} | Source: {source} | Time: {ts or 'N/A'}"


def _fmt_incident_from_record(i: Any) -> str:
    """Format a local_store IncidentRecord object."""
    severity = (getattr(i, "severity", "unknown") or "unknown").upper()
    title = getattr(i, "title", "Untitled") or "Untitled"
    region = getattr(i, "region", "Unknown") or "Unknown"
    risk = getattr(i, "risk_score", 0) or 0
    source_info = getattr(i, "source_info", {})
    if isinstance(source_info, dict):
        source = source_info.get("name", "Unknown")
    else:
        source = getattr(source_info, "name", "Unknown")
    created_at = getattr(i, "created_at", None)
    ts = ""
    if created_at:
        try:
            if isinstance(created_at, str):
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            else:
                dt = created_at
            ts = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            ts = str(created_at)[:19]
    return f"- [{severity}] {title} | Region: {region} | Risk: {float(risk):.1f} | Source: {source} | Time: {ts or 'N/A'}"


def _sort_key_incident_dict(i: dict) -> str:
    return i.get("createdAt") or i.get("created_at") or ""


def _sort_key_incident_record(i: Any) -> str:
    v = getattr(i, "created_at", None)
    return str(v) if v else ""


def _build_system_prompt(
    incidents_from_context: list[dict],
    alerts_from_context: list[dict],
    store_incidents: list,
    store_alerts: list,
    store_risk: list,
    last_updated: str,
) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Incidents: prefer frontend context (matches dashboard exactly) ──
    if incidents_from_context:
        sorted_incidents = sorted(incidents_from_context, key=_sort_key_incident_dict, reverse=True)
        incident_lines = "\n".join(_fmt_incident_from_dict(i) for i in sorted_incidents[:20])
        incident_source_note = f"(from live dashboard as of {last_updated or today})"
    else:
        sorted_store = sorted(store_incidents, key=_sort_key_incident_record, reverse=True)
        incident_lines = "\n".join(_fmt_incident_from_record(i) for i in sorted_store[:20])
        incident_source_note = "(from backend store)"

    incident_lines = incident_lines or "No incidents currently loaded."

    # ── Alerts ──
    if alerts_from_context:
        alert_lines = "\n".join(
            f"- [{(a.get('severity') or 'unknown').upper()}] {a.get('title', 'Alert')} | Region: {a.get('region', 'Unknown')}"
            for a in alerts_from_context[:10]
        )
    else:
        alert_lines = "\n".join(
            f"- [{(getattr(a, 'severity', 'unknown') or 'unknown').upper()}] {getattr(a, 'title', 'Alert')} | Region: {getattr(a, 'region', 'Unknown')}"
            for a in store_alerts[:10]
        )
    alert_lines = alert_lines or "No active alerts."

    # ── Risk scores ──
    risk_lines = "\n".join(
        f"- {r.region}: {r.overall_score:.1f}/100"
        for r in sorted(store_risk, key=lambda x: x.overall_score, reverse=True)[:8]
    ) or "No risk scores available."

    return f"""You are CrisisShield AI — an elite crisis intelligence analyst embedded in the CrisisShield real-time security operations platform for Lebanon. You are the primary AI advisor to a professional security operations team monitoring Lebanese territory 24/7.

Current date and time: {today}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IDENTITY & EXPERTISE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You combine the knowledge of:
- A senior Lebanon geopolitical analyst with 20+ years of field experience
- A military intelligence officer specialising in Levant security dynamics
- A real-time crisis operations coordinator with access to live dashboard feeds

You have deep, encyclopedic knowledge of:
• Lebanese political system: confessionalism, parliament, cabinet formation, constitutional rules
• All major political parties and movements: Hezbollah, Amal, Future Movement, Lebanese Forces, Kataeb, FPM, PSP, Marada, LF, and all others
• Armed factions and their military structure, weapons, territorial control, and alliances
• Key figures — past and present: politicians, militia leaders, religious authorities, military commanders
• Lebanon's sectarian geography: which regions are controlled or influenced by which factions
• Regional dynamics: Israel-Lebanon conflict, Syria spillover, Palestinian factions in Lebanon, Iranian influence, Saudi influence, US/French involvement
• Lebanese Armed Forces (LAF), Internal Security Forces (ISF), and their capabilities and limitations
• Historical events: Civil War (1975–1990), Israeli occupations, 2006 war, Beirut port explosion (2020), economic collapse, 2024 Israeli military operations

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURRENT POLITICAL LEADERSHIP (as of {today})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• President: Joseph Aoun — elected January 9, 2025 (ended 26-month vacancy after Michel Aoun's term)
• Prime Minister: Nawaf Salam — appointed January 2025, former president of the International Court of Justice
• Hezbollah Secretary-General: Hassan Nasrallah was killed September 27, 2024. Leadership succession ongoing.
• Speaker of Parliament: Nabih Berri (Amal Movement, long-serving since 1992)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LIVE DASHBOARD DATA {incident_source_note}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTIVE INCIDENTS (sorted newest first, each with exact timestamp):
{incident_lines}

ACTIVE ALERTS:
{alert_lines}

REGIONAL RISK SCORES (0–100):
{risk_lines}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPONSE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. ANSWER FREELY — You answer any Lebanon-related question: people, factions, geography, history, military, politics, religion, economics, culture. Never refuse a Lebanon question.

2. LIVE DATA PRIORITY — For questions about current incidents, alerts, or regional risk levels, anchor your answer in the live dashboard data above. The data above is the SAME data currently displayed on the user's dashboard screen.

3. USE EXACT TIMESTAMPS — Every incident above has a "Time:" field with its exact timestamp. Always report these exact times when asked about when something happened. Never say you don't have dates — they are in the data above.

4. KNOWLEDGE CONFIDENCE — Use your full training knowledge confidently. Do not say "my knowledge only goes to 2024." You know about Nasrallah's death (Sept 27, 2024), Aoun's election (Jan 9, 2025), and the 2024 Israeli military operations in Lebanon.

5. INTELLIGENCE ANALYST TONE — Be direct, precise, and analytical. Lead with the key finding. Use structured markdown (headers, bullets, bold) for clarity. Avoid long preambles.

6. OPERATIONAL RELEVANCE — Where appropriate, connect your answer to operational implications for security teams: threat levels, recommended monitoring areas, credibility of sources.

7. UNCERTAINTY LABELLING — If something genuinely occurred after August 2025, state this clearly. Say: "I don't have confirmed information beyond August 2025 on this specific point."

8. BREVITY — Keep answers concise and scannable. Use bullet points for lists. A good intelligence brief is short and actionable."""


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    settings = get_settings()

    if not settings.claude_api_key:
        return ChatResponse(
            answer="The AI chat feature requires a Claude API key. Please set `CLAUDE_API_KEY` in the backend `.env` file.",
            model="none",
        )

    # Extract frontend live context (matches exactly what the dashboard shows)
    ctx = request.context
    incidents_from_context: list[dict] = ctx.get("incidents") or []
    alerts_from_context: list[dict] = ctx.get("alerts") or []
    last_updated: str = ctx.get("lastUpdated") or ""
    logger.info("Chat: %d incidents from frontend context, %d alerts", len(incidents_from_context), len(alerts_from_context))

    # Fetch store data for risk scores and as fallback for incidents/alerts.
    # In postgres mode local_store may be empty — supplement with live news cache.
    store_incidents = local_store.list_incidents()
    if not store_incidents:
        try:
            from app.services.live_news import live_news_service
            store_incidents = live_news_service._cache or []
        except Exception:
            store_incidents = []
    store_alerts = local_store.list_alerts()
    store_risk = local_store.list_risk_scores()
    logger.info("Chat fallback: %d store incidents, %d risk scores", len(store_incidents), len(store_risk))

    system_prompt = _build_system_prompt(
        incidents_from_context=incidents_from_context,
        alerts_from_context=alerts_from_context,
        store_incidents=store_incidents,
        store_alerts=store_alerts,
        store_risk=store_risk,
        last_updated=last_updated,
    )

    # Build message list for Claude
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
