"""In-process fan-out for side integrations (the Notion mirror today).

The call loop publishes facts here ("a lead changed", "the call ended") and
never learns who listens. That keeps third-party APIs off the hot path: a
voice turn must not wait on Notion, so every subscriber runs on a small
background pool, and a subscriber that fails is logged, never raised.

Events and their payloads (all JSON-safe dicts):

    lead_upserted        {"session_id", "mode", "lead": {...}}
    call_ended           {"session_id", "mode", "outcome", "summary": {...} | None,
                          "products": [catalog ids mentioned on the call]}
    product_spotlighted  {"session_id", "mode", "product": {...catalog entry}}
    mode_changed         {"session_id", "mode", "previous", "by": "voice" | "console"}
    meeting_booked       {"session_id", "mode", "booking": {...}}
    objection_logged     {"session_id", "mode", "objection": {...}}
"""
from __future__ import annotations

import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger("zuno.integrations")

Handler = Callable[[dict[str, Any]], None]

EVENTS = (
    "lead_upserted",
    "call_ended",
    "product_spotlighted",
    "mode_changed",
    "meeting_booked",
    "objection_logged",
)

_subscribers: dict[str, list[Handler]] = defaultdict(list)
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="zuno-integrations")
# Tests flip this so handlers run inline and assertions see their effects.
run_inline = False


def subscribe(event: str, handler: Handler) -> None:
    if event not in EVENTS:
        raise ValueError(f"unknown integration event: {event}")
    _subscribers[event].append(handler)


def emit(event: str, payload: dict[str, Any]) -> None:
    for handler in list(_subscribers.get(event, ())):
        if run_inline:
            _run(event, handler, payload)
        else:
            _pool.submit(_run, event, handler, payload)


def clear() -> None:
    _subscribers.clear()


def _run(event: str, handler: Handler, payload: dict[str, Any]) -> None:
    try:
        handler(payload)
    except Exception:
        logger.warning("integration handler for %s failed", event, exc_info=True)
