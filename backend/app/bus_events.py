"""One place that stamps session_id and mode onto every integration event.

The bus itself (app/integrations/bus.py) is fire-and-forget on its own pool,
so emitting from the turn path costs a queue append, never a network call.
This wrapper adds the two fields every subscriber relies on and makes sure a
broken bus can never fail a turn.
"""
from __future__ import annotations

import logging
from typing import Any

from app.integrations import bus

logger = logging.getLogger("zuno.integrations")


def emit(event: str, session: Any, **fields: Any) -> None:
    payload = {
        "session_id": getattr(session, "session_id", None),
        "mode": getattr(session, "mode", None),
        **fields,
    }
    try:
        bus.emit(event, payload)
    except Exception:
        logger.warning("integration emit %s failed", event, exc_info=True)
