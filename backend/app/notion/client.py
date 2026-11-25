"""Small synchronous client for the Notion REST API.

Synchronous because its callers are the integration bus's background threads
and a one-shot setup script, neither of which has an event loop. Two things
it owns so callers do not have to:

1. Pace. Notion allows about three requests a second per connection, and the
   workspace-wide budget (180 a minute below Business plans) is shared with
   Graphify reading the same workspace. One lock-guarded slot schedule paces
   every thread sharing a client.
2. Retries. 429 (honouring Retry-After), 409 conflict_error (Notion's own
   advice is to retry it), 5xx and network errors back off and retry. Any
   other 4xx is a bug in the request and raises at once.

Pinned to a Notion-Version that uses data sources: a database is a container
and its rows live in a data source, so queries, new rows and relation targets
all take a data source id.
"""
from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterator

import httpx

from app.notion.config import DEFAULT_NOTION_VERSION
from app.notion.schema import ZUNO_ID

logger = logging.getLogger("zuno.notion")

NOTION_API = "https://api.notion.com/v1"
_RETRY_STATUSES = {409, 429, 500, 502, 503, 504}


class NotionError(RuntimeError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"Notion {status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message

    @classmethod
    def from_response(cls, response: httpx.Response) -> "NotionError":
        try:
            body = response.json()
        except ValueError:
            body = {}
        return cls(response.status_code, body.get("code", ""), body.get("message", response.text[:200]))


@dataclass
class UpsertResult:
    page_id: str
    created: bool
    # The row as it was before this write, when it had to be looked up.
    # None for a create, or when the caller already knew the page id.
    previous: dict | None = None


class NotionClient:
    def __init__(
        self,
        token: str,
        *,
        version: str = DEFAULT_NOTION_VERSION,
        max_rps: float = 2.5,
        max_retries: int = 5,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.version = version
        self._http = httpx.Client(
            base_url=NOTION_API,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": version,
                "Content-Type": "application/json",
            },
            timeout=timeout,
            transport=transport,
        )
        self._interval = 1.0 / max_rps if max_rps > 0 else 0.0
        self._max_retries = max_retries
        self._sleep = sleep
        self._clock = clock
        self._slot_lock = threading.Lock()
        self._next_slot = 0.0

    def close(self) -> None:
        self._http.close()

    # --- transport -----------------------------------------------------------

    def _wait_for_slot(self) -> None:
        with self._slot_lock:
            now = self._clock()
            start = max(now, self._next_slot)
            self._next_slot = start + self._interval
        if start > now:
            self._sleep(start - now)

    def _backoff(self, attempt: int, response: httpx.Response | None) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return min(60.0, max(0.0, float(retry_after)))
                except ValueError:
                    pass
        return min(30.0, 0.5 * 2**attempt) + random.uniform(0, 0.25)

    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | list | None = None,
    ) -> dict:
        for attempt in range(self._max_retries + 1):
            self._wait_for_slot()
            response: httpx.Response | None = None
            try:
                response = self._http.request(method, path, json=json, params=params)
            except httpx.TransportError as exc:
                if attempt >= self._max_retries:
                    raise NotionError(0, "network_error", str(exc)) from exc
                logger.info("Notion %s %s network error, retrying", method, path)
                self._sleep(self._backoff(attempt, None))
                continue
            if response.status_code in _RETRY_STATUSES and attempt < self._max_retries:
                delay = self._backoff(attempt, response)
                logger.info(
                    "Notion %s %s -> %s, retrying in %.1fs", method, path, response.status_code, delay
                )
                self._sleep(delay)
                continue
            if response.status_code >= 400:
                raise NotionError.from_response(response)
            return response.json() if response.content else {}
        raise AssertionError("unreachable")  # pragma: no cover

    def _paginate(self, method: str, path: str, body: dict | None = None) -> Iterator[dict]:
        cursor: str | None = None
        while True:
            if method == "GET":
                params = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
                data = self.request("GET", path, params=params)
            else:
                payload = {**(body or {}), "page_size": 100}
                if cursor:
                    payload["start_cursor"] = cursor
                data = self.request(method, path, json=payload)
            yield from data.get("results", [])
            cursor = data.get("next_cursor")
            if not data.get("has_more") or not cursor:
                return

    # --- databases and data sources --------------------------------------

    def create_database(
        self,
        parent_page_id: str,
        title: str,
        properties: dict[str, dict],
        *,
        icon: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Create a database under a page. Returns the database object, with
        its data_sources list filled in even when the create response was the
        partial form the API is allowed to return."""
        body: dict[str, Any] = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "initial_data_source": {"properties": properties},
        }
        if icon:
            body["icon"] = {"type": "emoji", "emoji": icon}
        if description:
            body["description"] = [{"type": "text", "text": {"content": description}}]
        database = self.request("POST", "/databases", json=body)
        if not database.get("data_sources"):
            database = self.retrieve_database(database["id"])
        return database

    def retrieve_database(self, database_id: str) -> dict:
        return self.request("GET", f"/databases/{database_id}")

    def retrieve_data_source(self, data_source_id: str) -> dict:
        return self.request("GET", f"/data_sources/{data_source_id}")

    def update_data_source(self, data_source_id: str, properties: dict[str, dict | None]) -> dict:
        return self.request("PATCH", f"/data_sources/{data_source_id}", json={"properties": properties})

    def query_data_source(self, data_source_id: str, filter: dict | None = None) -> Iterator[dict]:
        body = {"filter": filter} if filter else {}
        return self._paginate("POST", f"/data_sources/{data_source_id}/query", body)

    # --- pages -----------------------------------------------------------

    def find_by_zuno_id(self, data_source_id: str, zuno_id: str) -> dict | None:
        data = self.request(
            "POST",
            f"/data_sources/{data_source_id}/query",
            json={
                "filter": {"property": ZUNO_ID, "rich_text": {"equals": zuno_id}},
                "page_size": 1,
            },
        )
        results = data.get("results") or []
        return results[0] if results else None

    def zuno_index(self, data_source_id: str) -> dict[str, str]:
        """Every row's ZUNO ID -> page id, in a handful of paged queries.
        Lets a bulk seed decide create-or-update without one query per row."""
        index: dict[str, str] = {}
        for page in self.query_data_source(data_source_id):
            key = plain_text(page.get("properties", {}).get(ZUNO_ID))
            if key:
                index.setdefault(key, page["id"])
        return index

    def create_page(
        self,
        data_source_id: str,
        properties: dict[str, dict],
        *,
        children: list[dict] | None = None,
        icon: str | None = None,
    ) -> dict:
        body: dict[str, Any] = {
            "parent": {"type": "data_source_id", "data_source_id": data_source_id},
            "properties": properties,
        }
        if children:
            body["children"] = children[:100]
        if icon:
            body["icon"] = {"type": "emoji", "emoji": icon}
        page = self.request("POST", "/pages", json=body)
        if children and len(children) > 100:
            self.append_children(page["id"], children[100:])
        return page

    def create_child_page(
        self, parent_page_id: str, title: str, *, children: list[dict] | None = None, icon: str | None = None
    ) -> dict:
        body: dict[str, Any] = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}},
        }
        if children:
            body["children"] = children[:100]
        if icon:
            body["icon"] = {"type": "emoji", "emoji": icon}
        page = self.request("POST", "/pages", json=body)
        if children and len(children) > 100:
            self.append_children(page["id"], children[100:])
        return page

    def retrieve_page(self, page_id: str) -> dict:
        return self.request("GET", f"/pages/{page_id}")

    def update_page(self, page_id: str, properties: dict[str, dict]) -> dict:
        return self.request("PATCH", f"/pages/{page_id}", json={"properties": properties})

    def upsert_page(
        self,
        data_source_id: str,
        zuno_id: str,
        properties: dict[str, dict],
        *,
        children: list[dict] | None = None,
        icon: str | None = None,
        page_id: str | None = None,
    ) -> UpsertResult:
        """Update the row whose ZUNO ID matches, or create it. `children` are
        only written on create; an update never touches the body."""
        props = {**properties, ZUNO_ID: {"rich_text": [{"type": "text", "text": {"content": zuno_id}}]}}
        if page_id:
            self.update_page(page_id, props)
            return UpsertResult(page_id, created=False)
        existing = self.find_by_zuno_id(data_source_id, zuno_id)
        if existing is not None:
            self.update_page(existing["id"], props)
            return UpsertResult(existing["id"], created=False, previous=existing)
        page = self.create_page(data_source_id, props, children=children, icon=icon)
        return UpsertResult(page["id"], created=True)

    def relation_ids(self, page: dict, prop_name: str) -> list[str]:
        """All page ids in a relation property. A page object lists at most 25
        and flags has_more; the property endpoint pages through the rest."""
        prop = page.get("properties", {}).get(prop_name) or {}
        ids = [item["id"] for item in prop.get("relation") or []]
        if not prop.get("has_more"):
            return ids
        ids = []
        cursor: str | None = None
        while True:
            params = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
            data = self.request("GET", f"/pages/{page['id']}/properties/{prop['id']}", params=params)
            ids += [item["relation"]["id"] for item in data.get("results", []) if item.get("relation")]
            cursor = data.get("next_cursor")
            if not data.get("has_more") or not cursor:
                return ids

    def set_relation(self, page_id: str, prop_name: str, page_ids: list[str]) -> None:
        ids = list(dict.fromkeys(page_ids))[:100]
        self.update_page(page_id, {prop_name: {"relation": [{"id": i} for i in ids]}})

    def add_relation(self, page_id: str, prop_name: str, page_ids: list[str]) -> list[str]:
        """Add to a relation without dropping what is there (a write replaces
        the whole list). Returns the merged list; skips the write when
        nothing is new."""
        current = self.relation_ids(self.retrieve_page(page_id), prop_name)
        merged = list(dict.fromkeys([*current, *page_ids]))
        if len(merged) == len(current):
            return current
        if len(merged) > 100:
            logger.info("relation %s is over Notion's 100-per-write cap, keeping the newest", prop_name)
            merged = merged[-100:]
        self.set_relation(page_id, prop_name, merged)
        return merged

    # --- blocks ----------------------------------------------------------

    def list_children(self, block_id: str) -> list[dict]:
        return list(self._paginate("GET", f"/blocks/{block_id}/children"))

    def append_children(self, block_id: str, children: list[dict]) -> None:
        for start in range(0, len(children), 100):
            self.request(
                "PATCH", f"/blocks/{block_id}/children", json={"children": children[start : start + 100]}
            )

    def delete_block(self, block_id: str) -> None:
        self.request("DELETE", f"/blocks/{block_id}")


def plain_text(prop: dict | None) -> str:
    """Plain text of a title or rich_text property value."""
    if not prop:
        return ""
    items = prop.get("title") if prop.get("type") == "title" else prop.get("rich_text")
    if items is None:
        items = prop.get("title") or prop.get("rich_text") or []
    return "".join(item.get("plain_text") or item.get("text", {}).get("content", "") for item in items)


def is_trashed(obj: dict) -> bool:
    return bool(obj.get("in_trash") or obj.get("archived") or obj.get("is_archived"))
