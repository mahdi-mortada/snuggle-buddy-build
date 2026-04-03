from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.config import get_settings
from app.db.elasticsearch import elasticsearch_client
from app.db.mongodb import mongodb_client
from app.db.postgres import postgres_client
from app.db.redis import redis_client
from app.services.local_store import local_store
from app.services.live_news import live_news_service
from app.services.nlp_pipeline import nlp_pipeline
from app.services.websocket_manager import websocket_manager
from app.workers.kafka_consumer import kafka_consumer

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize storage
    local_store.initialize()
    # Connect databases
    await postgres_client.connect()
    await mongodb_client.connect()
    await elasticsearch_client.connect()
    await redis_client.connect()
    # Start real-time services
    await websocket_manager.start()
    # Initialize NLP pipeline (loads models)
    await nlp_pipeline.initialize()
    # Populate dashboard state with current live incidents in postgres mode.
    if settings.storage_mode == "postgres":
        await live_news_service.sync_current_incidents()
    # Start Kafka consumer
    await kafka_consumer.start()
    yield
    # Shutdown
    await kafka_consumer.stop()
    await websocket_manager.stop()
    await postgres_client.disconnect()
    await mongodb_client.disconnect()
    await elasticsearch_client.disconnect()
    await redis_client.disconnect()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_v1_router, prefix="/api/v1")

# Prometheus metrics endpoint at /metrics
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app)
except ImportError:
    pass


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "success": True,
        "data": {
            "storage_mode": settings.storage_mode,
            "postgres": await postgres_client.ping(),
            "mongodb": await mongodb_client.ping(),
            "elasticsearch": await elasticsearch_client.ping(),
            "redis": await redis_client.ping(),
            "seeded_users": len(local_store.list_users()),
            "seeded_incidents": len(local_store.list_incidents()),
        },
        "error": None,
    }


@app.websocket("/ws/live-feed")
async def live_feed(websocket: WebSocket) -> None:
    await websocket_manager.connect(websocket)
    try:
        await websocket.send_json(
            {
                "type": "snapshot",
                "data": {
                    "incidents": [incident.model_dump(mode="json") for incident in local_store.list_incidents()[:10]],
                    "alerts": [alert.model_dump(mode="json") for alert in local_store.list_alerts()[:10]],
                },
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
