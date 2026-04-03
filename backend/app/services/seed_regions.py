"""Seed Lebanon regions from GeoJSON into PostgreSQL regions table.

Run once after running Alembic migrations:
    python -m app.services.seed_regions
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

from app.config import get_settings
from app.db.postgres import postgres_client

logger = logging.getLogger(__name__)

GEOJSON_PATH = Path(__file__).parents[2] / "data" / "lebanon_boundaries.geojson"


async def seed_regions() -> int:
    """Load Lebanon boundaries into the regions table. Returns count inserted."""
    settings = get_settings()
    await postgres_client.connect()

    if not postgres_client.is_connected:
        logger.error("PostgreSQL not connected — cannot seed regions")
        return 0

    with open(GEOJSON_PATH, encoding="utf-8") as f:
        geojson = json.load(f)

    features = geojson.get("features", [])
    inserted = 0
    skipped = 0

    async with postgres_client.session_scope() as session:
        from sqlalchemy import text

        for feature in features:
            props = feature["properties"]
            geom = feature.get("geometry")

            region_id = props.get("id") or str(uuid.uuid4())
            name = props["name"]
            name_ar = props.get("name_ar", "")
            region_type = props["type"]
            centroid_lat = props.get("centroid_lat")
            centroid_lng = props.get("centroid_lng")

            # Convert GeoJSON geometry to WKT for PostGIS
            if geom:
                coords = geom["coordinates"][0]
                coord_str = ", ".join(f"{lng} {lat}" for lng, lat in coords)
                wkt = f"POLYGON(({coord_str}))"
            else:
                wkt = None

            # Check if already exists
            result = await session.execute(
                text("SELECT id FROM regions WHERE name = :name"),
                {"name": name},
            )
            if result.fetchone():
                skipped += 1
                continue

            if wkt:
                await session.execute(
                    text(
                        """
                        INSERT INTO regions (id, name, name_ar, type, geom, centroid, centroid_lat, centroid_lng)
                        VALUES (
                            :id, :name, :name_ar, :type,
                            ST_GeomFromText(:wkt, 4326),
                            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                            :lat, :lng
                        )
                        """
                    ),
                    {
                        "id": region_id,
                        "name": name,
                        "name_ar": name_ar,
                        "type": region_type,
                        "wkt": wkt,
                        "lat": centroid_lat,
                        "lng": centroid_lng,
                    },
                )
            else:
                await session.execute(
                    text(
                        """
                        INSERT INTO regions (id, name, name_ar, type, centroid_lat, centroid_lng)
                        VALUES (:id, :name, :name_ar, :type, :lat, :lng)
                        """
                    ),
                    {
                        "id": region_id,
                        "name": name,
                        "name_ar": name_ar,
                        "type": region_type,
                        "lat": centroid_lat,
                        "lng": centroid_lng,
                    },
                )
            inserted += 1

    logger.info("Regions seeded: %d inserted, %d skipped", inserted, skipped)
    return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = asyncio.run(seed_regions())
    print(f"Done: {count} regions seeded")
