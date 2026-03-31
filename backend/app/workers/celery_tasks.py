from __future__ import annotations

from app.services.local_store import local_store


async def recalculate_risk_scores() -> None:
    local_store.recalculate()
