"""An in-memory stand-in for the slice of the Notion API the mirror uses.

Plugged in through httpx.MockTransport, so the real NotionClient (headers,
pacing, retries, JSON shapes) runs against it unchanged. It is strict where a
real workspace would be: a property the data source does not have, or a value
whose type does not match the schema, is a 400 - which is how the tests catch
an encoder writing a select into a status property.

No tests live here; the other test_notion_* files import it.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

import httpx

from app.notion.client import NotionClient

_VALUE_TYPES = {
    "title", "rich_text", "number", "select", "multi_select", "status", "date",
    "url", "email", "phone_number", "checkbox", "relation",
}


def _new_id() -> str:
    return str(uuid.uuid4())


def _plain(items: list[dict]) -> list[dict]:
    out = []
    for item in items or []:
        item = json.loads(json.dumps(item))
        if item.get("type") == "text":
            item["plain_text"] = item["text"]["content"]
        elif item.get("type") == "mention":
            item["plain_text"] = "@page"
        out.append(item)
    return out


class FakeNotion:
    def __init__(
        self,
        *,
        reject_status: bool = False,
        partial_database_response: bool = False,
        reject_database_links: bool = False,
    ) -> None:
        self.reject_status = reject_status
        self.reject_database_links = reject_database_links
        self.partial_database_response = partial_database_response
        self.databases: dict[str, dict] = {}
        self.data_sources: dict[str, dict] = {}
        self.pages: dict[str, dict] = {}
        self.children: dict[str, list[dict]] = {}
        self.calls: list[tuple[str, str, Any]] = []
        # Status codes to answer the next requests with, before normal service.
        self.fail_next: list[tuple[int, dict]] = []
        self.parent_page_id = _new_id()
        self.pages[self.parent_page_id] = {
            "id": self.parent_page_id,
            "parent": {"type": "workspace", "workspace": True},
            "properties": {"title": {"title": [{"type": "text", "text": {"content": "ZUNO"}}]}},
            "in_trash": False,
        }
        self.children[self.parent_page_id] = []

    # --- wiring ----------------------------------------------------------

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def client(self, **kwargs: Any) -> NotionClient:
        kwargs.setdefault("max_rps", 0)
        kwargs.setdefault("sleep", lambda _s: None)
        return NotionClient("ntn_test", transport=self.transport(), **kwargs)

    def count(self, method: str, pattern: str) -> int:
        return sum(1 for m, p, _ in self.calls if m == method and re.fullmatch(pattern, p))

    # --- queries for assertions -------------------------------------------

    def rows(self, data_source_id: str) -> list[dict]:
        return [
            p for p in self.pages.values()
            if p["parent"].get("data_source_id") == data_source_id and not p["in_trash"]
        ]

    def row(self, data_source_id: str, zuno_id: str) -> dict:
        matches = [p for p in self.rows(data_source_id) if self.text(p, "ZUNO ID") == zuno_id]
        assert len(matches) == 1, f"{len(matches)} rows with ZUNO ID {zuno_id}"
        return matches[0]

    @staticmethod
    def text(page: dict, prop: str) -> str:
        value = page["properties"].get(prop) or {}
        items = value.get("title") or value.get("rich_text") or []
        return "".join(i.get("text", {}).get("content", "") for i in items)

    @staticmethod
    def relation(page: dict, prop: str) -> list[str]:
        return [r["id"] for r in (page["properties"].get(prop) or {}).get("relation", [])]

    @staticmethod
    def option(page: dict, prop: str) -> str | None:
        value = page["properties"].get(prop) or {}
        for kind in ("select", "status"):
            if value.get(kind):
                return value[kind]["name"]
        return None

    # --- HTTP ------------------------------------------------------------

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/v1")
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, path, body))
        if self.fail_next:
            status, headers = self.fail_next.pop(0)
            return httpx.Response(status, json={"code": "rate_limited", "message": "slow down"}, headers=headers)
        try:
            return self._route(request.method, path, body, request)
        except _ApiError as exc:
            return httpx.Response(exc.status, json={"object": "error", "code": exc.code, "message": exc.message})

    def _route(self, method: str, path: str, body: Any, request: httpx.Request) -> httpx.Response:
        parts = path.strip("/").split("/")
        if parts == ["databases"] and method == "POST":
            return self._json(self._create_database(body))
        if parts[0] == "databases" and len(parts) == 2 and method == "GET":
            return self._json(self._database(parts[1]))
        if parts[0] == "data_sources" and len(parts) == 2:
            if method == "GET":
                return self._json(self._data_source(parts[1]))
            if method == "PATCH":
                return self._json(self._update_data_source(parts[1], body))
        if parts[0] == "data_sources" and len(parts) == 3 and parts[2] == "query" and method == "POST":
            return self._json(self._query(parts[1], body or {}))
        if parts == ["pages"] and method == "POST":
            return self._json(self._create_page(body))
        if parts[0] == "pages" and len(parts) == 2:
            if method == "GET":
                return self._json(self._render(self._page(parts[1])))
            if method == "PATCH":
                return self._json(self._update_page(parts[1], body))
        if parts[0] == "blocks" and len(parts) == 3 and parts[2] == "children":
            if method == "GET":
                return self._json(self._list_children(parts[1], request))
            if method == "PATCH":
                return self._json(self._append(parts[1], body))
        if parts[0] == "blocks" and len(parts) == 2 and method == "DELETE":
            return self._json(self._delete_block(parts[1]))
        raise _ApiError(400, "invalid_request_url", f"no fake route for {method} {path}")

    @staticmethod
    def _json(data: Any) -> httpx.Response:
        return httpx.Response(200, json=data)

    # --- databases -------------------------------------------------------

    def _create_database(self, body: dict) -> dict:
        parent = body["parent"]["page_id"]
        if parent not in self.pages:
            raise _ApiError(404, "object_not_found", "parent page not shared")
        properties = body["initial_data_source"]["properties"]
        if self.reject_status and any("status" in schema for schema in properties.values()):
            raise _ApiError(400, "validation_error", "status options are not supported")
        title = body["title"][0]["text"]["content"]
        database_id, ds_id = _new_id(), _new_id()
        self.databases[database_id] = {
            "object": "database",
            "id": database_id,
            "title": body["title"],
            "parent": body["parent"],
            "data_sources": [{"id": ds_id, "name": title}],
            "in_trash": False,
        }
        self.data_sources[ds_id] = {
            "object": "data_source",
            "id": ds_id,
            "title": title,
            "parent": {"type": "database_id", "database_id": database_id},
            "properties": {},
            "in_trash": False,
        }
        for name, schema in properties.items():
            self._add_property(ds_id, name, schema)
        self.children[parent].append(
            {"object": "block", "id": database_id, "type": "child_database", "child_database": {"title": title}}
        )
        if self.partial_database_response:
            return {"object": "database", "id": database_id}
        return self.databases[database_id]

    def _add_property(self, ds_id: str, name: str, schema: dict) -> None:
        kind = next(iter(schema))
        prop = {"id": _new_id()[:4], "name": name, "type": kind, kind: json.loads(json.dumps(schema[kind]))}
        if kind == "relation":
            target = schema["relation"]["data_source_id"]
            if target not in self.data_sources:
                raise _ApiError(400, "validation_error", "relation target not found")
            if schema["relation"].get("type") == "dual_property":
                source_title = self.data_sources[ds_id]["title"]
                reverse_name = f"Related to {source_title} ({name})"
                reverse = {
                    "id": _new_id()[:4],
                    "name": reverse_name,
                    "type": "relation",
                    "relation": {
                        "data_source_id": ds_id,
                        "type": "dual_property",
                        "dual_property": {"synced_property_name": name, "synced_property_id": prop["id"]},
                    },
                }
                self.data_sources[target]["properties"][reverse_name] = reverse
                prop["relation"]["dual_property"] = {
                    "synced_property_name": reverse_name,
                    "synced_property_id": reverse["id"],
                }
        self.data_sources[ds_id]["properties"][name] = prop

    def _database(self, database_id: str) -> dict:
        if database_id not in self.databases:
            raise _ApiError(404, "object_not_found", "no such database")
        return self.databases[database_id]

    def _data_source(self, ds_id: str) -> dict:
        if ds_id not in self.data_sources:
            raise _ApiError(404, "object_not_found", "no such data source")
        return self.data_sources[ds_id]

    def _update_data_source(self, ds_id: str, body: dict) -> dict:
        source = self._data_source(ds_id)
        for key, change in body.get("properties", {}).items():
            current_name = next(
                (n for n, p in source["properties"].items() if n == key or p["id"] == key), None
            )
            if change is None:
                if current_name:
                    del source["properties"][current_name]
                continue
            if set(change) == {"name"}:
                if current_name is None:
                    raise _ApiError(400, "validation_error", f"no property {key}")
                prop = source["properties"].pop(current_name)
                prop["name"] = change["name"]
                source["properties"][change["name"]] = prop
                continue
            if self.reject_status and "status" in change:
                raise _ApiError(400, "validation_error", "status options are not supported")
            self._add_property(ds_id, key, change)
        return source

    def _query(self, ds_id: str, body: dict) -> dict:
        self._data_source(ds_id)
        rows = self.rows(ds_id)
        flt = body.get("filter")
        if flt:
            wanted = flt["rich_text"]["equals"]
            rows = [r for r in rows if self.text(r, flt["property"]) == wanted]
        size = body.get("page_size", 100)
        start = int(body.get("start_cursor") or 0)
        chunk = rows[start : start + size]
        more = start + size < len(rows)
        return {
            "object": "list",
            "results": [self._render(r) for r in chunk],
            "has_more": more,
            "next_cursor": str(start + size) if more else None,
        }

    # --- pages -----------------------------------------------------------

    def _check_properties(self, ds_id: str, properties: dict) -> None:
        schema = self.data_sources[ds_id]["properties"]
        for name, value in properties.items():
            if name not in schema:
                raise _ApiError(400, "validation_error", f"{name} is not a property that exists")
            kind = next(iter(value))
            if kind not in _VALUE_TYPES or kind != schema[name]["type"]:
                raise _ApiError(400, "validation_error", f"{name} is a {schema[name]['type']}, not {kind}")
            if kind == "relation":
                for item in value["relation"]:
                    if item["id"] not in self.pages:
                        raise _ApiError(400, "validation_error", "related page not found")

    def _create_page(self, body: dict) -> dict:
        parent = body["parent"]
        page_id = _new_id()
        if parent.get("type") == "data_source_id":
            self._data_source(parent["data_source_id"])
            self._check_properties(parent["data_source_id"], body["properties"])
        else:
            self._page(parent["page_id"])
            title = body["properties"]["title"]["title"][0]["text"]["content"]
            self.children[parent["page_id"]].append(
                {"object": "block", "id": page_id, "type": "child_page", "child_page": {"title": title}}
            )
        self.pages[page_id] = {
            "id": page_id,
            "parent": parent,
            "properties": json.loads(json.dumps(body["properties"])),
            "in_trash": False,
        }
        try:
            self.children[page_id] = [self._block(b) for b in body.get("children", [])]
        except _ApiError:
            del self.pages[page_id]
            if parent.get("type") == "page_id":
                self.children[parent["page_id"]].pop()
            raise
        return self._render(self.pages[page_id])

    def _page(self, page_id: str) -> dict:
        if page_id not in self.pages:
            raise _ApiError(404, "object_not_found", "no such page")
        return self.pages[page_id]

    def _update_page(self, page_id: str, body: dict) -> dict:
        page = self._page(page_id)
        if page["parent"].get("type") == "data_source_id":
            self._check_properties(page["parent"]["data_source_id"], body.get("properties", {}))
        page["properties"].update(json.loads(json.dumps(body.get("properties", {}))))
        return self._render(page)

    def _render(self, page: dict) -> dict:
        props = {}
        for name, value in page["properties"].items():
            kind = next(iter(value))
            rendered: dict[str, Any] = {"id": name[:4], "type": kind}
            if kind in ("title", "rich_text"):
                rendered[kind] = _plain(value[kind])
            else:
                rendered[kind] = json.loads(json.dumps(value[kind]))
            if kind == "relation":
                rendered["has_more"] = False
            props[name] = rendered
        return {"object": "page", "id": page["id"], "parent": page["parent"], "properties": props,
                "in_trash": page["in_trash"]}

    # --- blocks ----------------------------------------------------------

    def _block(self, block: dict) -> dict:
        if self.reject_database_links and (block.get("link_to_page") or {}).get("type") == "database_id":
            raise _ApiError(400, "validation_error", "link_to_page database_id is not supported")
        return {**json.loads(json.dumps(block)), "id": _new_id()}

    def _list_children(self, block_id: str, request: httpx.Request) -> dict:
        items = self.children.get(block_id)
        if items is None:
            raise _ApiError(404, "object_not_found", "no such block")
        size = int(request.url.params.get("page_size", 100))
        start = int(request.url.params.get("start_cursor") or 0)
        more = start + size < len(items)
        return {
            "object": "list",
            "results": items[start : start + size],
            "has_more": more,
            "next_cursor": str(start + size) if more else None,
        }

    def _append(self, block_id: str, body: dict) -> dict:
        if block_id not in self.children:
            raise _ApiError(404, "object_not_found", "no such block")
        new = [self._block(b) for b in body["children"]]
        self.children[block_id].extend(new)
        return {"object": "list", "results": new}

    def _delete_block(self, block_id: str) -> dict:
        for items in self.children.values():
            for block in list(items):
                if block["id"] == block_id:
                    items.remove(block)
                    return {**block, "in_trash": True}
        raise _ApiError(404, "object_not_found", "no such block")


class _ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


SAMPLE_CATALOGS = {
    "apple": [
        {
            "id": "apple-macbook-air-m5",
            "brand": "Apple",
            "name": "MacBook Air (M5)",
            "line": "MacBook Air",
            "category": "mac",
            "subcategory": "mac",
            "gender": None,
            "family": None,
            "notes": None,
            "key_ingredients": [],
            "description": "13-inch, 18-hour battery.",
            "sizes": [{"label": "13-inch", "price_usd": 999}],
            "price_usd_from": 999,
            "image_url": None,
            "url": None,
            "stock": None,
        }
    ],
    "perfume": [
        {
            "id": "dior-sauvage-eau-de-parfum",
            "brand": "Dior",
            "name": "Sauvage Eau de Parfum",
            "line": "Sauvage",
            "category": "fragrance",
            "subcategory": "eau de parfum",
            "gender": "men",
            "family": "Fresh Spicy",
            "notes": {"top": ["Calabrian bergamot"], "heart": ["Sichuan pepper"], "base": ["Ambroxan"]},
            "key_ingredients": [],
            "description": "Raw and noble.",
            "sizes": [{"label": "100 ml", "price_hkd": 1250}],
            "price_hkd_from": 1250,
            "image_url": "https://example.com/sauvage.jpg",
            "url": "https://www.dior.com/en_hk/beauty/sauvage",
            "stock": 12,
        },
        {
            "id": "dior-jadore-eau-de-parfum",
            "brand": "Dior",
            "name": "J'adore Eau de Parfum",
            "line": "J'adore",
            "category": "fragrance",
            "subcategory": "eau de parfum",
            "gender": "women",
            "family": "Floral, Fruity",
            "notes": {"top": ["Calabrian Bergamot"], "heart": ["Damascus rose"], "base": []},
            "key_ingredients": [],
            "description": "A bouquet.",
            "sizes": [{"label": "50 ml", "price_hkd": 990}],
            "price_hkd_from": 990,
            "image_url": None,
            "url": None,
            "stock": 3,
        },
        {
            "id": "dior-rouge-dior",
            "brand": "Dior",
            "name": "Rouge Dior",
            "line": "Rouge Dior",
            "category": "makeup",
            "subcategory": "lipstick",
            "gender": None,
            "family": None,
            "notes": None,
            "key_ingredients": ["floral lip care"],
            "description": "Couture lipstick.",
            "sizes": [],
            "price_hkd_from": None,
            "image_url": None,
            "url": None,
            "stock": 20,
        },
    ],
}
