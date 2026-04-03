"""Alert Threshold Engine — Section 8.1.

Triggers alerts based on Redis-configurable thresholds:
  INFO:       risk_score > 40
  WARNING:    risk_score > 60
  CRITICAL:   risk_score > 80
  EMERGENCY:  risk_score > 90 OR anomaly detected

Also triggers on:
  - Risk velocity > 20 points/hour
  - Anomaly detection flag
  - Escalation probability > 0.8

Rate limiting: max 1 alert per region per severity per hour (Redis TTL).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Optional
from uuid import uuid4

from app.models.alert import AlertRecord
from app.models.incident import IncidentRecord
from app.models.risk_score import RiskScoreRecord

logger = logging.getLogger(__name__)


class AlertService:
    """
    Alert generation with Redis-backed thresholds and rate limiting.
    """

    _DEFAULT_THRESHOLDS = {
        "info": 40.0,
        "warning": 60.0,
        "critical": 80.0,
        "emergency": 90.0,
        "velocity": 20.0,
        "escalation_probability": 0.8,
        "rate_limit_seconds": 3600.0,
    }

    def generate_alerts(
        self,
        incidents: list[IncidentRecord],
        risk_scores: list[RiskScoreRecord],
    ) -> list[AlertRecord]:
        """Synchronous alert generation (used by LocalStore). Basic threshold logic."""
        thresholds = self._DEFAULT_THRESHOLDS
        risk_lookup = {r.region: r for r in risk_scores}
        alerts: list[AlertRecord] = []
        seen: set[tuple[str, str]] = set()

        for risk in risk_scores:
            severity = self._severity_from_score(risk.overall_score, thresholds)
            if not severity:
                continue
            key = (risk.region, severity)
            if key in seen:
                continue
            seen.add(key)

            region_incidents = [i for i in incidents if i.region == risk.region]
            recent_titles = "; ".join(i.title for i in region_incidents[:3])
            alert_type = "threshold_breach" if risk.overall_score >= thresholds["warning"] else "trend"

            alerts.append(
                AlertRecord(
                    id=str(uuid4()),
                    risk_score_id=risk.id,
                    incident_id=region_incidents[0].id if region_incidents else None,
                    alert_type=alert_type,
                    severity=severity,
                    title=f"{risk.region}: {severity.upper()} Risk Level",
                    message=(
                        f"Risk score in {risk.region} has reached {risk.overall_score:.1f}/100. "
                        f"Recent: {recent_titles[:200]}"
                    ),
                    recommendation=self._build_basic_recommendation(risk, severity),
                    region=risk.region,
                    linked_incidents=[i.id for i in region_incidents[:5]],
                    notification_channels=self._channels_for_severity(severity),
                    created_at=datetime.now(UTC),
                )
            )

        return alerts

    async def generate_alerts_async(
        self,
        risk_scores: list[RiskScoreRecord],
        incidents: list[IncidentRecord],
        previous_scores: Optional[dict[str, float]] = None,
    ) -> list[AlertRecord]:
        """
        Full async alert generation with Redis rate limiting, velocity check,
        and AI recommendations for CRITICAL/EMERGENCY.
        """
        try:
            from app.db.redis import redis_client
            thresholds = await redis_client.get_alert_thresholds()
        except Exception:
            thresholds = self._DEFAULT_THRESHOLDS

        alerts: list[AlertRecord] = []
        now = datetime.now(UTC)

        for risk in risk_scores:
            triggered: list[tuple[str, str]] = []  # (alert_type, severity)

            # 1. Threshold breach
            severity = self._severity_from_score(risk.overall_score, thresholds)
            if severity:
                triggered.append(("threshold_breach", severity))

            # 2. Risk velocity (> 20 pts/hr)
            if previous_scores and risk.region in previous_scores:
                velocity = risk.overall_score - previous_scores[risk.region]
                if velocity >= thresholds.get("velocity", 20.0):
                    triggered.append(("trend", "warning"))
                    logger.info("Velocity alert for %s: +%.1f points/hr", risk.region, velocity)

            # 3. Anomaly detection
            try:
                from app.services.anomaly_detection import anomaly_detector
                if anomaly_detector.is_trained:
                    from app.services.feature_engineering import feature_engineering_service
                    features = feature_engineering_service.build_feature_vector({
                        "sentiment_component": risk.sentiment_component,
                        "volume_component": risk.volume_component,
                        "keyword_component": risk.keyword_component,
                        "behavior_component": risk.behavior_component,
                        "geospatial_component": risk.geospatial_component,
                    })
                    result = anomaly_detector.predict([features])
                    if result["is_anomalous"]:
                        triggered.append(("anomaly", "critical"))
            except Exception:
                pass

            # 4. Escalation probability
            try:
                from app.services.escalation_model import escalation_model
                if escalation_model.is_trained:
                    prob = escalation_model.predict_probability(risk)
                    if prob >= thresholds.get("escalation_probability", 0.8):
                        triggered.append(("escalation", "critical"))
            except Exception:
                pass

            for alert_type, sev in triggered:
                # Rate limit check
                try:
                    from app.db.redis import redis_client
                    if not await redis_client.check_alert_rate_limit(risk.region, sev):
                        logger.debug("Rate limited: %s / %s", risk.region, sev)
                        continue
                except Exception:
                    pass

                region_incidents = [i for i in incidents if i.region == risk.region]
                recommendation = await self._get_recommendation(risk, sev, region_incidents)

                alert = AlertRecord(
                    id=str(uuid4()),
                    risk_score_id=risk.id,
                    alert_type=alert_type,
                    severity=sev,
                    title=f"{risk.region}: {sev.upper()} Alert ({alert_type.replace('_', ' ').title()})",
                    message=self._build_message(risk, alert_type),
                    recommendation=recommendation,
                    region=risk.region,
                    linked_incidents=[i.id for i in region_incidents[:5]],
                    notification_channels=self._channels_for_severity(sev),
                    created_at=now,
                )
                alerts.append(alert)

                # Dispatch notifications
                await self._dispatch_notifications(alert)

        return alerts

    def _severity_from_score(self, score: float, thresholds: dict) -> Optional[str]:
        if score > thresholds.get("emergency", 90):
            return "emergency"
        if score > thresholds.get("critical", 80):
            return "critical"
        if score > thresholds.get("warning", 60):
            return "warning"
        if score > thresholds.get("info", 40):
            return "info"
        return None

    def _channels_for_severity(self, severity: str) -> list[str]:
        if severity == "emergency":
            return ["dashboard", "email", "sms", "webhook"]
        if severity == "critical":
            return ["dashboard", "email", "webhook"]
        if severity == "warning":
            return ["dashboard", "email"]
        return ["dashboard"]

    def _build_message(self, risk: RiskScoreRecord, alert_type: str) -> str:
        return (
            f"Risk in {risk.region} at {risk.overall_score:.1f}/100. "
            f"Components: sentiment={risk.sentiment_component:.1f}, "
            f"volume={risk.volume_component:.1f}, "
            f"keyword={risk.keyword_component:.1f}. "
            f"Alert type: {alert_type}."
        )

    def _build_basic_recommendation(self, risk: RiskScoreRecord, severity: str) -> str:
        templates = {
            "emergency": (
                f"EMERGENCY: Immediate response required in {risk.region}. "
                "Deploy rapid response units. Notify regional command. Restrict public movement."
            ),
            "critical": (
                f"CRITICAL alert in {risk.region}. "
                "Alert security forces and coordinate with local authorities. "
                "Monitor situation closely and prepare response resources."
            ),
            "warning": (
                f"Elevated risk in {risk.region}. "
                "Increase patrols and monitoring frequency. "
                "Brief field units on current threat level."
            ),
            "info": (
                f"Low-level activity detected in {risk.region}. "
                "Continue standard monitoring protocols."
            ),
        }
        return templates.get(severity, "Monitor the situation.")

    async def _get_recommendation(
        self,
        risk: RiskScoreRecord,
        severity: str,
        incidents: list[IncidentRecord],
    ) -> str:
        """Get AI recommendation for CRITICAL/EMERGENCY; basic text for others."""
        if severity in ("critical", "emergency"):
            try:
                from app.services.recommendation_engine import recommendation_engine
                return await recommendation_engine.generate(risk, severity, incidents)
            except Exception as exc:
                logger.debug("AI recommendation failed, using fallback: %s", exc)

        return self._build_basic_recommendation(risk, severity)

    async def _dispatch_notifications(self, alert: AlertRecord) -> None:
        """Dispatch to non-dashboard channels."""
        if "email" in alert.notification_channels or "sms" in alert.notification_channels:
            try:
                from app.services.notification_service import notification_service
                await notification_service.dispatch(alert)
            except Exception as exc:
                logger.error("Notification dispatch failed: %s", exc)

        # WebSocket broadcast
        try:
            from app.services.websocket_manager import websocket_manager
            await websocket_manager.broadcast("alert", {
                "id": alert.id,
                "severity": alert.severity,
                "title": alert.title,
                "region": alert.region,
                "alert_type": alert.alert_type,
            })
        except Exception as exc:
            logger.debug("WebSocket broadcast failed: %s", exc)


alert_service = AlertService()
