from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from typing import Any

logger = logging.getLogger("app.system_events")


def log_system_event(level: str, event: str, details: dict[str, Any]) -> None:
    normalized_level = level.upper()
    payload = {
        "level": normalized_level,
        "event": event,
        "details": details,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    message = json.dumps(payload, ensure_ascii=True, default=str)

    if normalized_level == "ERROR":
        logger.error(message)
        return
    if normalized_level == "WARN":
        logger.warning(message)
        return
    logger.info(message)
