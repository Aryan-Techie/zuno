"""Builders for page-body blocks.

Bodies matter to Graphify in two ways. An @-mention or a "link to page" block
in a body is an edge in the graph, as long as it is not buried deep inside
toggles or columns (Graphify follows nested blocks only to a limited depth),
so links here are always top-level blocks. And a page with no content at all
comes back from Notion with no title and shows as "Untitled", so every page
ZUNO creates gets at least one paragraph.
"""
from __future__ import annotations

from app.notion.schema import text_items


def text(content: str, *, url: str | None = None, bold: bool = False) -> list[dict]:
    items = text_items(content)
    for item in items:
        if url:
            item["text"]["link"] = {"url": url}
        if bold:
            item["annotations"] = {"bold": True}
    return items


def mention(page_id: str) -> list[dict]:
    return [{"type": "mention", "mention": {"type": "page", "page": {"id": page_id}}}]


def paragraph(*parts: list[dict]) -> dict:
    rich: list[dict] = [item for part in parts for item in part][:100]
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich}}


def heading(content: str, level: int = 2) -> dict:
    kind = f"heading_{level}"
    return {"object": "block", "type": kind, kind: {"rich_text": text_items(content)}}


def bullet(*parts: list[dict]) -> dict:
    rich: list[dict] = [item for part in parts for item in part][:100]
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": rich},
    }


def callout(content: str, emoji: str = "💡") -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {"rich_text": text_items(content), "icon": {"type": "emoji", "emoji": emoji}},
    }


def divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def link_to_page(page_id: str) -> dict:
    return {
        "object": "block",
        "type": "link_to_page",
        "link_to_page": {"type": "page_id", "page_id": page_id},
    }


def link_to_database(database_id: str) -> dict:
    return {
        "object": "block",
        "type": "link_to_page",
        "link_to_page": {"type": "database_id", "database_id": database_id},
    }
