"""AI Recommendation Engine — Section 8.2.

For CRITICAL and EMERGENCY alerts, uses LangChain + Claude API to generate:
  - Situation summary (2-3 sentences)
  - Immediate actions (3-5 bullet points)
  - Resource deployment suggestions
  - Public communication guidance

Results are cached in Redis (TTL 1 hour) to avoid redundant API calls.
Falls back to a structured template when Claude API is unavailable.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from app.models.incident import IncidentRecord
from app.models.risk_score import RiskScoreRecord

logger = logging.getLogger(__name__)

CACHE_TTL = 3600  # 1 hour


class RecommendationEngine:
    """LangChain + Claude recommendation generator with Redis caching."""

    def build_recommendation(self, incident: IncidentRecord, overall_score: float) -> str:
        """Sync fallback used by legacy alert_service.generate_alerts."""
        actions = [
            f"Coordinate with regional responders in {incident.region}.",
            "Verify the incident with at least one additional trusted source.",
            "Prepare a public communication update if the situation escalates.",
        ]
        if overall_score >= 80:
            actions.insert(0, "Activate critical-response coordination and notify senior decision makers.")
        elif overall_score >= 60:
            actions.insert(0, "Increase monitoring and stage response resources near the affected area.")
        return " ".join(actions)

    async def generate(
        self,
        risk: RiskScoreRecord,
        severity: str,
        incidents: list[IncidentRecord],
    ) -> str:
        """
        Generate AI-powered recommendations for CRITICAL/EMERGENCY alerts.
        Caches results in Redis.
        """
        # Build cache key from region + score rounded to nearest 5
        rounded_score = round(risk.overall_score / 5) * 5
        cache_key = f"recommendation:{risk.region}:{severity}:{rounded_score}"

        # Check Redis cache first
        try:
            from app.db.redis import redis_client
            cached = await redis_client.get(cache_key)
            if cached:
                logger.debug("Recommendation cache hit: %s", cache_key)
                return cached
        except Exception:
            pass

        # Try Claude API via LangChain
        recommendation = await self._generate_with_claude(risk, severity, incidents)

        # Cache result
        try:
            from app.db.redis import redis_client
            await redis_client.setex(cache_key, CACHE_TTL, recommendation)
        except Exception:
            pass

        return recommendation

    async def _generate_with_claude(
        self,
        risk: RiskScoreRecord,
        severity: str,
        incidents: list[IncidentRecord],
    ) -> str:
        """Call Claude API via LangChain to generate recommendation."""
        from app.config import get_settings
        settings = get_settings()

        if not settings.claude_api_key:
            return self._fallback_recommendation(risk, severity)

        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage, SystemMessage

            # Build context
            recent_summaries = "\n".join(
                f"- [{i.category.upper()}] {i.title} (severity: {i.severity}, region: {i.region})"
                for i in incidents[:10]
            )

            system_prompt = (
                "You are a crisis management advisor for Lebanon. "
                "Your role is to provide concise, actionable security recommendations to authorities. "
                "Be direct, prioritize life safety, and respect Lebanon's regional context."
            )

            user_prompt = f"""
CRISIS ALERT: {severity.upper()} level in {risk.region}

Risk Score: {risk.overall_score:.1f}/100
Components:
- Sentiment risk: {risk.sentiment_component:.1f}/100
- Volume anomaly: {risk.volume_component:.1f}/100
- Threat keywords: {risk.keyword_component:.1f}/100
- Behavior patterns: {risk.behavior_component:.1f}/100
- Geographic density: {risk.geospatial_component:.1f}/100

Recent incidents in region:
{recent_summaries or "No recent incidents available"}

Please provide:
1. Situation summary (2-3 sentences)
2. Immediate recommended actions (3-5 bullet points)
3. Resource deployment suggestion (1-2 sentences)
4. Public communication guidance (1 sentence)

Be concise and actionable. Use plain text, no markdown headers.
"""

            llm = ChatAnthropic(
                model="claude-haiku-4-5-20251001",
                api_key=settings.claude_api_key,
                max_tokens=400,
                temperature=0.3,
            )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = await llm.ainvoke(messages)
            recommendation = response.content.strip()
            logger.info("Claude recommendation generated for %s (%s)", risk.region, severity)
            return recommendation

        except Exception as exc:
            logger.warning("Claude API call failed: %s — using fallback", exc)
            return self._fallback_recommendation(risk, severity)

    def _fallback_recommendation(self, risk: RiskScoreRecord, severity: str) -> str:
        """Structured fallback when Claude is unavailable."""
        templates = {
            "emergency": (
                f"EMERGENCY SITUATION in {risk.region} (risk: {risk.overall_score:.0f}/100). "
                "Situation summary: Multiple severe incidents have triggered an emergency risk level. "
                "Immediate actions: (1) Deploy rapid response units immediately. "
                "(2) Notify regional command and senior decision-makers. "
                "(3) Establish security perimeter if armed activity confirmed. "
                "(4) Restrict civilian movement in affected zone. "
                "(5) Coordinate with ISF and civil defense units. "
                "Resources: Pre-position emergency response teams at designated staging areas. "
                "Public comms: Issue immediate advisory for residents to stay indoors and await official guidance."
            ),
            "critical": (
                f"CRITICAL risk level in {risk.region} (risk: {risk.overall_score:.0f}/100). "
                "Situation summary: Risk indicators have crossed critical threshold. Situation requires immediate attention. "
                "Immediate actions: (1) Alert security forces in the region. "
                "(2) Coordinate with local authorities and municipality. "
                "(3) Increase intelligence gathering and source verification. "
                "(4) Brief field units on current threat assessment. "
                "Resources: Stage response resources within 15-minute deployment distance. "
                "Public comms: Monitor situation and prepare contingency announcement."
            ),
            "warning": (
                f"WARNING-level risk in {risk.region} (risk: {risk.overall_score:.0f}/100). "
                "Situation summary: Elevated activity detected requiring heightened vigilance. "
                "Immediate actions: (1) Increase patrol frequency. "
                "(2) Brief all units on current intelligence. "
                "(3) Verify and corroborate incoming incident reports. "
                "Resources: Maintain standard deployment with increased readiness. "
                "Public comms: No public announcement needed at this stage."
            ),
        }
        return templates.get(severity, f"Elevated risk in {risk.region}. Maintain standard monitoring protocols.")


recommendation_engine = RecommendationEngine()
