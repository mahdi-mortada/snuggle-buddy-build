"""Kafka Consumer Worker — Section 3.2.

Consumes raw-incidents topic:
  raw-incidents → NLP pipeline → feature engineering → risk scoring
  → store to PostgreSQL + Elasticsearch + local store
  → publish enriched record to processed-incidents topic
  → broadcast via WebSocket
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Optional

logger = logging.getLogger(__name__)

CONSUMER_GROUP = "crisisshield-processors"
TOPIC_RAW = "raw-incidents"
TOPIC_PROCESSED = "processed-incidents"


class KafkaConsumerWorker:
    """Async Kafka consumer that drives the NLP → risk pipeline."""

    def __init__(self) -> None:
        self._consumer = None
        self._producer = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start consuming in background. Non-fatal if Kafka is unavailable."""
        try:
            from confluent_kafka import Consumer, Producer, KafkaError

            from app.config import get_settings
            settings = get_settings()

            self._consumer = Consumer({
                "bootstrap.servers": settings.kafka_bootstrap_servers,
                "group.id": CONSUMER_GROUP,
                "auto.offset.reset": "latest",
                "enable.auto.commit": False,
            })
            self._consumer.subscribe([TOPIC_RAW])

            self._producer = Producer({
                "bootstrap.servers": settings.kafka_bootstrap_servers,
            })

            self._running = True
            self._task = asyncio.create_task(self._consume_loop())
            logger.info("Kafka consumer started on topic '%s'", TOPIC_RAW)
        except Exception as exc:
            logger.warning("Kafka consumer start failed (non-fatal): %s", exc)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._consumer:
            try:
                self._consumer.close()
            except Exception:
                pass
        logger.info("Kafka consumer stopped")

    async def _consume_loop(self) -> None:
        """Main consume loop — runs in background."""
        from confluent_kafka import KafkaError

        while self._running:
            try:
                # Poll in thread pool to avoid blocking event loop
                msg = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self._consumer.poll(timeout=1.0)
                )
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        logger.error("Kafka consumer error: %s", msg.error())
                    continue

                # Process message
                try:
                    payload = json.loads(msg.value().decode("utf-8"))
                    await self._process_message(payload)
                    # Commit offset after successful processing
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._consumer.commit
                    )
                except Exception as exc:
                    logger.error("Failed to process Kafka message: %s", exc)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Kafka consumer loop error: %s", exc)
                await asyncio.sleep(5)

    async def _process_message(self, payload: dict) -> None:
        """Full pipeline: raw data → NLP → features → store → broadcast."""
        from app.db.elasticsearch import elasticsearch_client
        from app.services.feature_engineering import feature_engineering_service
        from app.services.local_store import local_store
        from app.services.location_resolver import resolve_location
        from app.services.nlp_pipeline import nlp_pipeline
        from app.services.websocket_manager import websocket_manager

        raw_text = payload.get("text", "")
        if not raw_text:
            return

        # Step 1: NLP processing
        nlp_result = await nlp_pipeline.process(raw_text, metadata=payload)

        # Step 2: Location resolution
        gpe_entities = nlp_pipeline.get_gpe_entities(nlp_result.get("entities", []))
        location_result = await resolve_location(
            gps_lat=payload.get("geo", {}).get("lat"),
            gps_lng=payload.get("geo", {}).get("lng"),
            text_location=payload.get("location_name"),
            nlp_gpe_entities=gpe_entities,
        )

        # Step 3: Build incident record
        from app.models.incident import IncidentRecord, IncidentLocation, SourceInfoRecord
        incident_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        source_info = SourceInfoRecord(
            **{
                "name": payload.get("source", "unknown"),
                "type": "social_media",
                "credibility": "unverified",
                "credibilityScore": 0.3,
                "logoInitials": "UN",
            }
        )

        lat = payload.get("geo", {}).get("lat", location_result.get("lat", 33.8938))
        lng = payload.get("geo", {}).get("lng", location_result.get("lng", 35.5018))
        location_name = payload.get("location_name") or location_result.get("location_name") or location_result["region"]

        incident = IncidentRecord(
            id=incident_id,
            source=payload.get("source_type", "social_media"),
            source_id=payload.get("source_id"),
            source_url=payload.get("url"),
            title=payload.get("title") or raw_text[:100],
            description=raw_text[:500],
            raw_text=raw_text,
            processed_text=nlp_result.get("cleaned_text"),
            category=nlp_result.get("category", "other"),
            severity=_estimate_severity(nlp_result),
            location=IncidentLocation(lat=lat, lng=lng),
            location_name=location_name,
            region=location_result["region"],
            country="Lebanon",
            sentiment_score=nlp_result.get("sentiment_score", 0.0),
            risk_score=0.0,  # will be updated by risk scoring
            entities=[e["text"] for e in nlp_result.get("entities", [])],
            keywords=nlp_result.get("keywords", []),
            language=nlp_result.get("language", "ar"),
            is_verified=False,
            status="processing",
            processing_status="nlp_complete",
            verification_status="unverified",
            confidence_score=nlp_result.get("category_confidence"),
            metadata={
                "keyword_score": str(nlp_result.get("keyword_score", 0)),
                "emotion": nlp_result.get("emotion", "neutral"),
                "location_method": location_result["method"],
                "location_confidence": str(location_result["confidence"]),
            },
            source_info=source_info,
            created_at=now,
            updated_at=now,
        )

        # Step 4: Store to local store (triggers risk recalculation)
        created = local_store.create_incident(incident)

        # Step 5: Index in Elasticsearch
        if elasticsearch_client.is_connected:
            await elasticsearch_client.index_incident({
                "id": created.id,
                "title": created.title,
                "description": created.description,
                "raw_text": created.raw_text,
                "category": created.category,
                "severity": created.severity,
                "region": created.region,
                "risk_score": created.risk_score,
                "sentiment_score": created.sentiment_score,
                "confidence_score": created.confidence_score,
                "verification_status": created.verification_status,
                "entities": created.entities,
                "keywords": created.keywords,
                "source": created.source,
                "status": created.status,
                "language": created.language,
                "is_verified": created.is_verified,
                "location": {"lat": created.location.lat, "lon": created.location.lng},
                "created_at": created.created_at.isoformat(),
            })

        # Step 6: Publish to processed-incidents Kafka topic
        if self._producer:
            enriched = {
                "id": created.id,
                "region": created.region,
                "category": created.category,
                "severity": created.severity,
                "sentiment_score": created.sentiment_score,
                "risk_score": created.risk_score,
                "created_at": created.created_at.isoformat(),
            }
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._producer.produce(
                    TOPIC_PROCESSED,
                    json.dumps(enriched).encode("utf-8"),
                    callback=lambda err, _msg: logger.error("Kafka produce error: %s", err) if err else None,
                ),
            )

        # Step 7: WebSocket broadcast
        await websocket_manager.broadcast("incident", {
            "id": created.id,
            "title": created.title,
            "region": created.region,
            "severity": created.severity,
            "category": created.category,
            "risk_score": created.risk_score,
        })

        logger.info(
            "Processed incident %s: region=%s category=%s severity=%s",
            incident_id[:8],
            created.region,
            created.category,
            created.severity,
        )


def _estimate_severity(nlp_result: dict) -> str:
    """Estimate severity from NLP results when not explicitly provided."""
    keyword_score = nlp_result.get("keyword_score", 0.0)
    sentiment = nlp_result.get("sentiment_score", 0.0)
    category = nlp_result.get("category", "other")

    # High-danger categories
    if category in ("terrorism", "armed_conflict") or keyword_score > 70:
        return "critical"
    if category in ("violence", "natural_disaster") or keyword_score > 40:
        return "high"
    if sentiment < -0.5 or keyword_score > 20:
        return "medium"
    return "low"


kafka_consumer = KafkaConsumerWorker()
