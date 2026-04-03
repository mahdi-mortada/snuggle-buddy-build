"""Notification Service — Section 8.3.

Dispatches alerts via:
  - Email (SMTP via FastAPI-Mail) for CRITICAL and EMERGENCY
  - SMS (Twilio) for EMERGENCY only
  - Webhook (POST JSON) for all severity levels if configured

Channels are determined by alert.notification_channels field.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from app.config import get_settings
from app.models.alert import AlertRecord

logger = logging.getLogger(__name__)


class NotificationService:
    """Multi-channel alert notification dispatcher."""

    async def dispatch(self, alert: AlertRecord) -> None:
        """Dispatch alert to all configured channels."""
        channels = alert.notification_channels or ["dashboard"]

        if "email" in channels:
            await self._send_email(alert)

        if "sms" in channels:
            await self._send_sms(alert)

        if "webhook" in channels:
            await self._send_webhooks(alert)

    # ── Email ────────────────────────────────────────────────────────────────

    async def _send_email(self, alert: AlertRecord) -> None:
        settings = get_settings()

        if not settings.smtp_username or not settings.alert_email_recipients:
            logger.debug("Email not configured — skipping email notification")
            return

        recipients = [r.strip() for r in settings.alert_email_recipients.split(",") if r.strip()]
        if not recipients:
            return

        try:
            from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

            conf = ConnectionConfig(
                MAIL_USERNAME=settings.smtp_username,
                MAIL_PASSWORD=settings.smtp_password,
                MAIL_FROM=settings.smtp_from_email,
                MAIL_FROM_NAME=settings.smtp_from_name,
                MAIL_PORT=settings.smtp_port,
                MAIL_SERVER=settings.smtp_host,
                MAIL_STARTTLS=True,
                MAIL_SSL_TLS=False,
                USE_CREDENTIALS=True,
            )

            severity_emoji = {
                "info": "ℹ️",
                "warning": "⚠️",
                "critical": "🚨",
                "emergency": "🆘",
            }
            emoji = severity_emoji.get(alert.severity, "🔔")

            body = f"""
CrisisShield Alert — {alert.severity.upper()}

{emoji} {alert.title}

Region: {alert.region}
Alert Type: {alert.alert_type}
Severity: {alert.severity.upper()}
Time: {alert.created_at.strftime('%Y-%m-%d %H:%M UTC')}

MESSAGE:
{alert.message}

RECOMMENDATION:
{alert.recommendation or 'No recommendation available.'}

Alert ID: {alert.id}
---
CrisisShield Integrated Smart Security Tool
"""

            message = MessageSchema(
                subject=f"[CrisisShield {alert.severity.upper()}] {alert.title}",
                recipients=recipients,
                body=body,
                subtype=MessageType.plain,
            )

            fm = FastMail(conf)
            await fm.send_message(message)
            logger.info("Email sent for alert %s to %d recipients", alert.id[:8], len(recipients))
        except Exception as exc:
            logger.error("Email notification failed: %s", exc)

    # ── SMS ──────────────────────────────────────────────────────────────────

    async def _send_sms(self, alert: AlertRecord) -> None:
        settings = get_settings()

        if not settings.twilio_account_sid or not settings.alert_sms_recipients:
            logger.debug("SMS not configured — skipping SMS notification")
            return

        # Only send SMS for EMERGENCY alerts
        if alert.severity not in ("emergency",):
            return

        recipients = [r.strip() for r in settings.alert_sms_recipients.split(",") if r.strip()]
        if not recipients:
            return

        try:
            from twilio.rest import Client

            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            sms_body = (
                f"[CrisisShield EMERGENCY] {alert.region}: {alert.title}. "
                f"Risk: {alert.message[:100]}..."
            )

            for phone in recipients:
                try:
                    client.messages.create(
                        body=sms_body,
                        from_=settings.twilio_from_phone,
                        to=phone,
                    )
                    logger.info("SMS sent for alert %s to %s", alert.id[:8], phone[-4:])
                except Exception as exc:
                    logger.error("SMS to %s failed: %s", phone[-4:], exc)
        except Exception as exc:
            logger.error("Twilio SMS notification failed: %s", exc)

    # ── Webhook ──────────────────────────────────────────────────────────────

    async def _send_webhooks(self, alert: AlertRecord) -> None:
        settings = get_settings()

        if not settings.alert_webhook_urls:
            return

        urls = [u.strip() for u in settings.alert_webhook_urls.split(",") if u.strip()]
        if not urls:
            return

        payload = {
            "id": alert.id,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "title": alert.title,
            "message": alert.message,
            "recommendation": alert.recommendation,
            "region": alert.region,
            "created_at": alert.created_at.isoformat(),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            for url in urls:
                try:
                    response = await client.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json", "X-CrisisShield-Alert": "1"},
                    )
                    if response.status_code >= 400:
                        logger.warning("Webhook %s returned %d", url, response.status_code)
                    else:
                        logger.info("Webhook dispatched to %s", url)
                except Exception as exc:
                    logger.error("Webhook to %s failed: %s", url, exc)


notification_service = NotificationService()
