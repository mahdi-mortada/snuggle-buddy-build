"""Redis async client using redis-py with hiredis."""
from __future__ import annotations

import json
import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

# Redis key prefixes
KEY_RISK_WEIGHTS = "config:risk_weights"
KEY_ALERT_THRESHOLDS = "config:alert_thresholds"
KEY_THREAT_KEYWORDS = "config:threat_keywords"
KEY_DASHBOARD_CACHE = "cache:dashboard"
KEY_RISK_SCORE_PREFIX = "cache:risk:"  # + region name
KEY_ALERT_RATE_PREFIX = "alert_rate:"  # + region:severity


class RedisClient:
    def __init__(self) -> None:
        self._client = None

    async def connect(self) -> None:
        settings = get_settings()
        try:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._client.ping()
            # Load initial config into Redis
            await self._load_initial_config(settings)
            logger.info("Redis connected")
        except Exception as exc:
            logger.warning("Redis connection failed (non-fatal in local mode): %s", exc)
            self._client = None

    async def _load_initial_config(self, settings) -> None:
        """Seed Redis with configurable values from settings (only if not already set)."""
        # Risk weights
        if not await self._client.exists(KEY_RISK_WEIGHTS):
            weights = {
                "sentiment": str(settings.risk_weight_sentiment),
                "volume": str(settings.risk_weight_volume),
                "keyword": str(settings.risk_weight_keyword),
                "behavior": str(settings.risk_weight_behavior),
                "geospatial": str(settings.risk_weight_geospatial),
            }
            await self._client.hset(KEY_RISK_WEIGHTS, mapping=weights)

        # Alert thresholds
        if not await self._client.exists(KEY_ALERT_THRESHOLDS):
            thresholds = {
                "info": str(settings.alert_threshold_info),
                "warning": str(settings.alert_threshold_warning),
                "critical": str(settings.alert_threshold_critical),
                "emergency": str(settings.alert_threshold_emergency),
                "velocity": str(settings.alert_velocity_threshold),
                "escalation_probability": str(settings.alert_escalation_probability_threshold),
                "rate_limit_seconds": str(settings.alert_rate_limit_seconds),
            }
            await self._client.hset(KEY_ALERT_THRESHOLDS, mapping=thresholds)

        # Default threat keywords (Arabic + English)
        if not await self._client.exists(KEY_THREAT_KEYWORDS):
            keywords = {
                # English
                "bomb": "10", "explosion": "10", "shooting": "9", "gunfire": "9",
                "attack": "8", "armed": "8", "hostage": "10", "terror": "10",
                "riot": "7", "protest": "4", "clashes": "7", "militia": "8",
                "sniper": "9", "rocket": "9", "airstrike": "10",
                "earthquake": "8", "flood": "6", "fire": "5", "collapse": "7",
                "outbreak": "7", "epidemic": "8", "contamination": "7",
                "blackout": "5", "power outage": "5", "bridge collapse": "8",
                # Arabic transliterations (stored as unicode)
                "انفجار": "10", "إطلاق نار": "9", "هجوم": "8", "مسلح": "8",
                "احتجاز رهائن": "10", "إرهاب": "10", "أعمال شغب": "7",
                "اشتباكات": "7", "صاروخ": "9", "غارة جوية": "10",
                "زلزال": "8", "فيضان": "6", "حريق": "5",
                "انهيار": "7", "وباء": "8", "انقطاع كهرباء": "5",
            }
            await self._client.hset(KEY_THREAT_KEYWORDS, mapping=keywords)
        logger.info("Redis config initialized")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Redis disconnected")

    async def ping(self) -> bool:
        if not self._client:
            return False
        try:
            return await self._client.ping()
        except Exception:
            return False

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    # ── Generic helpers ──────────────────────────────────────────────────────

    async def get(self, key: str) -> str | None:
        if not self._client:
            return None
        return await self._client.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None) -> None:
        if not self._client:
            return
        data = json.dumps(value) if not isinstance(value, str) else value
        await self._client.set(key, data, ex=ex)

    async def delete(self, key: str) -> None:
        if not self._client:
            return
        await self._client.delete(key)

    async def hgetall(self, key: str) -> dict[str, str]:
        if not self._client:
            return {}
        return await self._client.hgetall(key) or {}

    async def hset(self, key: str, mapping: dict) -> None:
        if not self._client:
            return
        await self._client.hset(key, mapping=mapping)

    async def publish(self, channel: str, message: str) -> None:
        if not self._client:
            return
        await self._client.publish(channel, message)

    async def setex(self, key: str, seconds: int, value: Any) -> None:
        if not self._client:
            return
        data = json.dumps(value) if not isinstance(value, str) else value
        await self._client.setex(key, seconds, data)

    # ── Domain-specific helpers ──────────────────────────────────────────────

    async def get_risk_weights(self) -> dict[str, float]:
        raw = await self.hgetall(KEY_RISK_WEIGHTS)
        if not raw:
            settings = get_settings()
            return {
                "sentiment": settings.risk_weight_sentiment,
                "volume": settings.risk_weight_volume,
                "keyword": settings.risk_weight_keyword,
                "behavior": settings.risk_weight_behavior,
                "geospatial": settings.risk_weight_geospatial,
            }
        return {k: float(v) for k, v in raw.items()}

    async def get_alert_thresholds(self) -> dict[str, float]:
        raw = await self.hgetall(KEY_ALERT_THRESHOLDS)
        if not raw:
            settings = get_settings()
            return {
                "info": settings.alert_threshold_info,
                "warning": settings.alert_threshold_warning,
                "critical": settings.alert_threshold_critical,
                "emergency": settings.alert_threshold_emergency,
                "velocity": settings.alert_velocity_threshold,
                "escalation_probability": settings.alert_escalation_probability_threshold,
                "rate_limit_seconds": float(settings.alert_rate_limit_seconds),
            }
        return {k: float(v) for k, v in raw.items()}

    async def get_threat_keywords(self) -> dict[str, float]:
        raw = await self.hgetall(KEY_THREAT_KEYWORDS)
        return {k: float(v) for k, v in raw.items()}

    async def check_alert_rate_limit(self, region: str, severity: str) -> bool:
        """Returns True if alert is ALLOWED (not rate-limited), False if rate-limited."""
        thresholds = await self.get_alert_thresholds()
        rate_limit = int(thresholds.get("rate_limit_seconds", 3600))
        key = f"{KEY_ALERT_RATE_PREFIX}{region}:{severity}"
        if not self._client:
            return True
        existing = await self._client.get(key)
        if existing:
            return False  # rate-limited
        await self._client.setex(key, rate_limit, "1")
        return True

    async def cache_dashboard(self, data: dict, ttl: int = 60) -> None:
        await self.setex(KEY_DASHBOARD_CACHE, ttl, data)

    async def get_cached_dashboard(self) -> dict | None:
        val = await self.get(KEY_DASHBOARD_CACHE)
        if val:
            try:
                return json.loads(val)
            except Exception:
                return None
        return None

    async def cache_risk_score(self, region: str, score: dict, ttl: int = 300) -> None:
        await self.setex(f"{KEY_RISK_SCORE_PREFIX}{region}", ttl, score)

    async def get_cached_risk_score(self, region: str) -> dict | None:
        val = await self.get(f"{KEY_RISK_SCORE_PREFIX}{region}")
        if val:
            try:
                return json.loads(val)
            except Exception:
                return None
        return None


redis_client = RedisClient()
