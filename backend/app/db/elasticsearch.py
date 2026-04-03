"""Elasticsearch async client with Arabic analyzer and index management."""
from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

# Mapping for the incidents index with Arabic full-text support
INCIDENTS_INDEX_MAPPING = {
    "settings": {
        "analysis": {
            "analyzer": {
                "arabic_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "arabic_normalization", "arabic_stop", "arabic_stemmer"],
                },
                "arabic_english_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "arabic_normalization"],
                },
            },
            "filter": {
                "arabic_stop": {"type": "stop", "stopwords": "_arabic_"},
                "arabic_stemmer": {"type": "stemmer", "language": "arabic"},
                "arabic_normalization": {"type": "arabic_normalization"},
            },
        }
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": "arabic_english_analyzer",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "description": {"type": "text", "analyzer": "arabic_english_analyzer"},
            "raw_text": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
            },
            "category": {"type": "keyword"},
            "severity": {"type": "keyword"},
            "region": {"type": "keyword"},
            "country": {"type": "keyword"},
            "location": {"type": "geo_point"},
            "risk_score": {"type": "float"},
            "sentiment_score": {"type": "float"},
            "confidence_score": {"type": "float"},
            "verification_status": {"type": "keyword"},
            "entities": {"type": "keyword"},
            "keywords": {"type": "keyword"},
            "source": {"type": "keyword"},
            "status": {"type": "keyword"},
            "language": {"type": "keyword"},
            "is_verified": {"type": "boolean"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        }
    },
}


class ElasticsearchClient:
    def __init__(self) -> None:
        self._client = None

    async def connect(self) -> None:
        settings = get_settings()
        try:
            from elasticsearch import AsyncElasticsearch

            self._client = AsyncElasticsearch(
                settings.elasticsearch_url,
                request_timeout=30,
            )
            # Verify connection
            if not await self._client.ping():
                raise ConnectionError("Elasticsearch ping failed")

            # Ensure index exists with correct mapping
            await self._setup_index()
            logger.info("Elasticsearch connected")
        except Exception as exc:
            logger.warning("Elasticsearch connection failed (non-fatal in local mode): %s", exc)
            self._client = None

    async def _setup_index(self) -> None:
        if not self._client:
            return
        exists = await self._client.indices.exists(index="incidents")
        if not exists:
            await self._client.indices.create(
                index="incidents",
                body=INCIDENTS_INDEX_MAPPING,
            )
            logger.info("Elasticsearch 'incidents' index created")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Elasticsearch disconnected")

    async def ping(self) -> bool:
        if not self._client:
            return False
        try:
            return await self._client.ping()
        except Exception:
            return False

    @property
    def client(self):
        if not self._client:
            raise RuntimeError("Elasticsearch is not connected.")
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    async def index_incident(self, doc: dict) -> None:
        """Index a single incident document."""
        if not self.is_connected:
            return
        try:
            await self._client.index(
                index="incidents",
                id=doc.get("id"),
                document=doc,
            )
        except Exception as exc:
            logger.error("Failed to index incident %s: %s", doc.get("id"), exc)

    async def bulk_index_incidents(self, docs: list[dict]) -> None:
        """Bulk index incident documents (batch size 100)."""
        if not self.is_connected or not docs:
            return
        from elasticsearch.helpers import async_bulk

        actions = [
            {"_index": "incidents", "_id": d.get("id"), "_source": d}
            for d in docs
        ]
        for i in range(0, len(actions), 100):
            batch = actions[i : i + 100]
            try:
                await async_bulk(self._client, batch)
            except Exception as exc:
                logger.error("Bulk index failed for batch starting at %d: %s", i, exc)

    async def search_incidents(
        self,
        query: str | None = None,
        filters: dict | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict:
        """Full-text search + filter incidents."""
        if not self.is_connected:
            return {"hits": {"hits": [], "total": {"value": 0}}}

        must_clauses = []
        filter_clauses = []

        if query:
            must_clauses.append(
                {
                    "multi_match": {
                        "query": query,
                        "fields": ["title^3", "description^2", "raw_text"],
                        "analyzer": "arabic_english_analyzer",
                    }
                }
            )

        if filters:
            for field, value in filters.items():
                if value is not None:
                    if isinstance(value, list):
                        filter_clauses.append({"terms": {field: value}})
                    else:
                        filter_clauses.append({"term": {field: value}})

        es_query = {
            "query": {
                "bool": {
                    "must": must_clauses or [{"match_all": {}}],
                    "filter": filter_clauses,
                }
            },
            "sort": [{"created_at": {"order": "desc"}}],
            "from": (page - 1) * per_page,
            "size": per_page,
        }

        try:
            result = await self._client.search(index="incidents", body=es_query)
            return result.body if hasattr(result, "body") else dict(result)
        except Exception as exc:
            logger.error("Elasticsearch search failed: %s", exc)
            return {"hits": {"hits": [], "total": {"value": 0}}}


elasticsearch_client = ElasticsearchClient()
