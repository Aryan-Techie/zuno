"""Optional side integrations, wired at startup.

Each integration registers its own bus subscribers and decides for itself
whether it is configured; an unconfigured one registers nothing.
"""
import logging

logger = logging.getLogger("zuno.integrations")


def register_all() -> None:
    try:
        from app.notion.sync import register as register_notion
    except ImportError:
        return
    try:
        register_notion()
    except Exception:
        logger.warning("Notion integration failed to register", exc_info=True)
