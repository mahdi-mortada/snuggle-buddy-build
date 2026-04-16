"""One-time script: fetch live news and write to PostgreSQL."""
import asyncio, json, sys
sys.path.insert(0, '/app')

async def run():
    from app.services.live_news import live_news_service
    from app.db.postgres import postgres_client
    import sqlalchemy as sa

    await postgres_client.connect()

    incidents = await live_news_service.fetch_current_incidents(limit=50)
    print(f"Fetched {len(incidents)} live incidents")

    async with postgres_client._engine.begin() as conn:
        for i in incidents:
            src_info = json.dumps(i.source_info.model_dump() if i.source_info else {})
            await conn.execute(sa.text("""
                INSERT INTO incidents (id, source, source_id, source_url, title, description, raw_text,
                    category, severity, location_name, region, country, sentiment_score, risk_score,
                    entities, keywords, language, is_verified, status, processing_status,
                    verification_status, source_info, metadata, created_at, updated_at)
                VALUES (:id, :source, :source_id, :source_url, :title, :description, :raw_text,
                    :category, :severity, :location_name, :region, :country,
                    :sentiment_score, :risk_score, CAST(:entities AS jsonb), CAST(:keywords AS jsonb), :language,
                    :is_verified, :status, :processing_status, :verification_status,
                    CAST(:source_info AS jsonb), CAST(:metadata AS jsonb), :created_at, :updated_at)
                ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, updated_at=EXCLUDED.updated_at
            """), {
                'id': str(i.id), 'source': i.source,
                'source_id': (i.source_id or str(i.id))[:255],
                'source_url': i.source_url or '', 'title': i.title,
                'description': i.description or i.title, 'raw_text': i.raw_text or i.title,
                'category': i.category, 'severity': i.severity,
                'location_name': i.location_name or 'Lebanon', 'region': i.region or 'Beirut',
                'country': 'Lebanon',
                'sentiment_score': float(i.sentiment_score or 0),
                'risk_score': float(i.risk_score or 0),
                'entities': json.dumps(list(i.entities or [])),
                'keywords': json.dumps(list(i.keywords or [])),
                'language': i.language or 'en', 'is_verified': False,
                'status': i.status or 'new', 'processing_status': 'pending',
                'verification_status': 'unverified',
                'source_info': src_info, 'metadata': '{}',
                'created_at': i.created_at, 'updated_at': i.updated_at,
            })
    print(f"Done — {len(incidents)} rows written to incidents table in PostgreSQL.")
    await postgres_client.disconnect()

asyncio.run(run())
