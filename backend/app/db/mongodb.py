"""MongoDB async client using Motor."""
from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


class MongoDBClient:
    def __init__(self) -> None:
        self._client = None
        self._db = None

    async def connect(self) -> None:
        settings = get_settings()
        try:
            from motor.motor_asyncio import AsyncIOMotorClient

            self._client = AsyncIOMotorClient(
                settings.mongodb_url,
                serverSelectionTimeoutMS=5000,
            )
            # Extract DB name from URL or default to crisisshield
            db_name = settings.mongodb_url.rstrip("/").split("/")[-1] or "crisisshield"
            self._db = self._client[db_name]

            # Verify connection
            await self._client.admin.command("ping")

            # Create indexes
            await self._setup_indexes()
            logger.info("MongoDB connected to database '%s'", db_name)
        except Exception as exc:
            logger.warning("MongoDB connection failed (non-fatal in local mode): %s", exc)
            self._client = None
            self._db = None

    async def _setup_indexes(self) -> None:
        """Create required indexes including TTL for raw_data."""
        if not self._db:
            return
        from pymongo import ASCENDING, DESCENDING

        raw = self._db["raw_data"]
        await raw.create_index([("source", ASCENDING), ("collected_at", DESCENDING)])
        await raw.create_index([("processed", ASCENDING)])
        # TTL index: auto-delete raw documents after 90 days
        await raw.create_index(
            [("collected_at", ASCENDING)],
            expireAfterSeconds=90 * 24 * 3600,
            name="ttl_raw_data_90d",
        )

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("MongoDB disconnected")

    async def ping(self) -> bool:
        if not self._client:
            return False
        try:
            await self._client.admin.command("ping")
            return True
        except Exception:
            return False

    @property
    def db(self):
        """Return the Motor database handle."""
        if not self._db:
            raise RuntimeError("MongoDB is not connected.")
        return self._db

    @property
    def is_connected(self) -> bool:
        return self._db is not None

    def get_collection(self, name: str):
        return self.db[name]


mongodb_client = MongoDBClient()
