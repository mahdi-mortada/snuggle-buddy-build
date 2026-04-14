"""Celery Task Definitions — Section 11 Phase 5.

Scheduled tasks:
  - recalculate_risk_scores: every 15 minutes
  - retrain_prophet_models: daily at midnight
  - retrain_anomaly_detector: weekly
  - ingest_live_news: every 2 minutes
"""
from __future__ import annotations

import asyncio
import logging

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "crisisshield",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)

# ── Periodic schedule (beat) ─────────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    "recalculate-risk-every-15min": {
        "task": "app.workers.celery_tasks.task_recalculate_risk",
        "schedule": 60 * settings.risk_recalc_interval_minutes,
    },
    "ingest-live-news-every-2min": {
        "task": "app.workers.celery_tasks.task_ingest_live_news",
        "schedule": 120.0,
    },
    "retrain-prophet-daily": {
        "task": "app.workers.celery_tasks.task_retrain_prophet",
        "schedule": crontab(hour=0, minute=0),
    },
    "retrain-anomaly-weekly": {
        "task": "app.workers.celery_tasks.task_retrain_anomaly",
        "schedule": crontab(hour=2, minute=0, day_of_week=0),  # Sunday 02:00
    },
    "scan-hate-speech-every-30min": {
        "task": "app.workers.celery_tasks.task_scan_hate_speech",
        "schedule": 1800.0,  # every 30 minutes
    },
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run_async(coro) -> None:
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Tasks ────────────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.celery_tasks.task_recalculate_risk", bind=True, max_retries=3)
def task_recalculate_risk(self) -> dict:
    """Recalculate risk scores for all regions every 15 minutes."""
    try:
        from app.services.local_store import local_store
        from app.services.risk_scoring import risk_scoring_service

        scores, alerts = local_store.recalculate()

        logger.info(
            "Risk recalculation complete: %d scores, %d alerts",
            len(scores),
            len(alerts),
        )
        return {"scores": len(scores), "alerts": len(alerts)}
    except Exception as exc:
        logger.error("Risk recalculation failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.workers.celery_tasks.task_ingest_live_news", bind=True, max_retries=2)
def task_ingest_live_news(self) -> dict:
    """Fetch live news every 2 minutes and process through NLP pipeline."""
    try:
        async def _run():
            from app.services.live_news import live_news_service
            return await live_news_service.sync_current_incidents(limit=10)

        count = _run_async(_run())
        logger.info(
            "Live news ingestion: fetched=%d inserted=%d updated=%d",
            count["fetched"],
            count["inserted"],
            count["updated"],
        )
        return count
    except Exception as exc:
        logger.error("Live news ingestion failed: %s", exc)
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="app.workers.celery_tasks.task_retrain_prophet", bind=True)
def task_retrain_prophet(self) -> dict:
    """Retrain Prophet forecasting models daily at midnight."""
    try:
        async def _run():
            from app.services.prediction_engine import prediction_engine
            count = await prediction_engine.train_all_regions()
            return count

        count = _run_async(_run())
        logger.info("Prophet retrained for %d regions", count)
        return {"regions_trained": count}
    except Exception as exc:
        logger.error("Prophet retraining failed: %s", exc)
        raise


@celery_app.task(name="app.workers.celery_tasks.task_retrain_anomaly", bind=True)
def task_retrain_anomaly(self) -> dict:
    """Retrain Isolation Forest anomaly detector weekly."""
    try:
        async def _run():
            from app.services.anomaly_detection import anomaly_detector
            await anomaly_detector.train_from_incidents()

        _run_async(_run())
        logger.info("Anomaly detector retrained")
        return {"status": "ok"}
    except Exception as exc:
        logger.error("Anomaly retraining failed: %s", exc)
        raise


@celery_app.task(name="app.workers.celery_tasks.task_scan_hate_speech", bind=True, max_retries=2)
def task_scan_hate_speech(self) -> dict:
    """Scrape X and run hate speech detection every 30 minutes."""
    try:
        async def _run():
            from app.services.social_monitor import social_monitor_service
            return await social_monitor_service.run_scan()

        result = _run_async(_run()) or {}
        logger.info("Hate speech scan: %s", result)
        return result or {"status": "ok"}
    except Exception as exc:
        logger.error("Hate speech scan failed: %s", exc)
        raise
