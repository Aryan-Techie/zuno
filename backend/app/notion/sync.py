"""Keeps the Notion mirror current while calls happen.

register() is called once at startup by app/integrations/register_all(). It
subscribes to the integration bus only when NOTION_TOKEN and every data source
id are set; otherwise it registers nothing and says so in one info line, and
the call loop never knows Notion exists.

Handlers run on the bus's background pool, two threads, so two events from
the same call can be in flight at once. Every write goes through a per-key
lock and an in-process ZUNO ID -> page id cache, which is what stops two
threads (or a query that has not caught up with a fresh create yet) from
writing the same call twice. A handler never raises: Notion being slow,
down, or misconfigured costs a missing node, not a failed turn.

What each event writes:

    lead_upserted        Lead row; the call's Lead relation and title
    product_spotlighted  Product row if it was never seeded; the product on
                         the call (Products mentioned) and on the lead
                         (Products of interest)
    objection_logged     Objection row linked to call, lead, product and its
                         playbook page; a resolved one adds its answer to the
                         playbook page with an @-mention of the product
    meeting_booked       Meeting row linked to lead and call
    mode_changed         The call's Mode, and a line in its body
    call_ended           Outcome, headline, next step, duration; the wrap-up
                         appended to the call's body
"""
from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from app.notion import blocks, records
from app.notion.catalog import (
    CatalogIndex,
    brand_key,
    family_key,
    family_names,
    mode_for,
    note_key,
    note_names,
)
from app.notion.client import NotionClient, UpsertResult
from app.notion.config import load_notion_settings
from app.notion.schema import SPECS, TITLE, ZUNO_ID, build_properties, zuno_id

logger = logging.getLogger("zuno.notion")

Handler = Callable[[dict[str, Any]], None]

_MAX_SESSIONS = 256


@dataclass
class _Session:
    started: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    lead_page: str | None = None
    lead_label: str | None = None
    call_label: str | None = None
    products: list[str] = field(default_factory=list)
    last_product: str | None = None
    # Objections logged before the caller was identified, waiting for a lead.
    orphan_objections: list[str] = field(default_factory=list)
    wrapped: bool = False


class NotionMirror:
    def __init__(
        self,
        client: NotionClient,
        data_sources: dict[str, str],
        *,
        catalog: CatalogIndex | None = None,
    ) -> None:
        self._client = client
        self._ds = data_sources
        self._catalog = catalog or CatalogIndex()
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}
        self._ids: dict[str, str] = {}
        self._sessions: OrderedDict[str, _Session] = OrderedDict()
        self._kinds: dict[str, dict[str, str]] = {}
        # (page id, relation) -> ids known to be on it, so a repeat spotlight
        # of the same product costs no request at all.
        self._relations: dict[tuple[str, str], set[str]] = {}
        self._resolved: set[str] = set()

    # --- wiring ----------------------------------------------------------

    def handlers(self) -> dict[str, Handler]:
        table: dict[str, Callable[[dict[str, Any]], None]] = {
            "lead_upserted": self.on_lead_upserted,
            "product_spotlighted": self.on_product_spotlighted,
            "objection_logged": self.on_objection_logged,
            "meeting_booked": self.on_meeting_booked,
            "mode_changed": self.on_mode_changed,
            "call_ended": self.on_call_ended,
        }
        return {event: self._safe(event, fn) for event, fn in table.items()}

    @staticmethod
    def _safe(event: str, fn: Callable[[dict[str, Any]], None]) -> Handler:
        def handler(payload: dict[str, Any]) -> None:
            try:
                fn(payload or {})
            except Exception as exc:
                logger.warning("Notion mirror skipped %s: %s", event, exc)
                logger.debug("Notion mirror %s traceback", event, exc_info=True)

        handler.__name__ = f"notion_{event}"
        return handler

    # --- plumbing --------------------------------------------------------

    def _lock(self, key: str) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = self._locks[key] = threading.Lock()
            return lock

    def _session(self, session_id: str | None) -> _Session:
        sid = session_id or "unknown"
        with self._guard:
            state = self._sessions.get(sid)
            if state is None:
                state = self._sessions[sid] = _Session()
                while len(self._sessions) > _MAX_SESSIONS:
                    self._sessions.popitem(last=False)
            else:
                self._sessions.move_to_end(sid)
            return state

    def _live_kinds(self, db: str) -> dict[str, str]:
        """Live types of the properties declared as Status. Setup falls back
        to a select when a workspace rejects a Status schema, and the value
        has to be written in whichever shape the property really has."""
        if db in self._kinds:
            return self._kinds[db]
        status_props = [p.name for p in SPECS[db].props if p.kind == "status"]
        if not status_props:
            self._kinds[db] = {}
            return {}
        schema = self._client.retrieve_data_source(self._ds[db]).get("properties", {})
        kinds = {name: schema[name]["type"] for name in status_props if name in schema and schema[name].get("type")}
        self._kinds[db] = kinds
        return kinds

    def _props(self, db: str, values: dict[str, Any]) -> dict[str, dict]:
        return build_properties(db, values, self._live_kinds(db))

    def _ensure(self, db: str, key: str, build: Callable[[], tuple[dict[str, Any], list[dict]]]) -> str:
        """Page id for `key`, creating the row from build() if it does not
        exist. Never rewrites an existing row."""
        cached = self._ids.get(key)
        if cached:
            return cached
        with self._lock(key):
            cached = self._ids.get(key)
            if cached:
                return cached
            page = self._client.find_by_zuno_id(self._ds[db], key)
            if page is None:
                values, children = build()
                page = self._client.create_page(
                    self._ds[db], self._props(db, {**values, ZUNO_ID: key}), children=children
                )
            self._ids[key] = page["id"]
            return page["id"]

    def _upsert(
        self,
        db: str,
        key: str,
        values: dict[str, Any],
        *,
        on_create: dict[str, Any] | None = None,
        children: list[dict] | None = None,
    ) -> UpsertResult:
        with self._lock(key):
            props = self._props(db, values)
            page_id = self._ids.get(key)
            if page_id:
                if props:
                    self._client.update_page(page_id, props)
                return UpsertResult(page_id, created=False)
            existing = self._client.find_by_zuno_id(self._ds[db], key)
            if existing is not None:
                if props:
                    self._client.update_page(existing["id"], props)
                self._ids[key] = existing["id"]
                return UpsertResult(existing["id"], created=False, previous=existing)
            create_props = self._props(db, {**(on_create or {}), **values, ZUNO_ID: key})
            page = self._client.create_page(self._ds[db], create_props, children=children)
            self._ids[key] = page["id"]
            return UpsertResult(page["id"], created=True)

    def _add_relation(self, page_id: str, prop: str, ids: list[str]) -> None:
        ids = [i for i in dict.fromkeys(ids) if i]
        if not ids:
            return
        slot = (page_id, prop)
        with self._lock(f"relation:{page_id}:{prop}"):
            known = self._relations.get(slot)
            if known is not None and set(ids) <= known:
                return
            merged = self._client.add_relation(page_id, prop, ids)
            self._relations[slot] = set(merged)

    # --- catalog pages ---------------------------------------------------

    def _brand_page(self, product: dict, mode: str) -> str | None:
        key = brand_key(product)
        if not key:
            return None
        name = str(product["brand"]).strip()
        return self._ensure(
            "brands", key, lambda: (records.brand_values(name, mode), records.brand_body(name))
        )

    def _family_pages(self, product: dict) -> list[str]:
        return [
            self._ensure(
                "families",
                family_key(name),
                lambda name=name: (records.family_values(name), records.family_body(name)),
            )
            for name in family_names(product)
        ]

    def _note_pages(self, product: dict) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for tier, names in note_names(product).items():
            for name in names:
                display = name[:1].upper() + name[1:]
                page = self._ensure(
                    "notes",
                    note_key(name),
                    lambda display=display, tier=tier: (
                        records.note_values(display, [tier]),
                        records.note_body(display),
                    ),
                )
                out.setdefault(tier, []).append(page)
        return out

    def _product_page(self, product: dict | None = None, *, product_id: str | None = None, mode: str | None = None) -> str | None:
        """Page id for a catalog product, creating it (and its brand, family
        and notes) when the seed never wrote it."""
        pid = (product or {}).get("id") or product_id
        if not pid:
            return None
        key = zuno_id("product", pid)
        cached = self._ids.get(key)
        if cached:
            return cached

        def build() -> tuple[dict[str, Any], list[dict]]:
            entry = product if product and product.get("name") else self._catalog.get(pid)
            if not entry:
                raise LookupError(f"product {pid} is not in any catalog")
            product_mode = mode_for(entry, entry.get("_mode") or mode)
            values = records.product_values(
                entry,
                product_mode,
                brand=self._brand_page(entry, product_mode),
                families=self._family_pages(entry),
                notes=self._note_pages(entry),
            )
            return values, records.product_body(entry)

        try:
            return self._ensure("products", key, build)
        except LookupError:
            logger.info("Notion mirror: product %s is not in a catalog, not linking it", pid)
            return None

    # --- call-scoped pages -----------------------------------------------

    def _call_page(self, session_id: str | None, mode: str | None) -> str:
        state = self._session(session_id)
        return self._ensure(
            "calls",
            records.call_key(session_id),
            lambda: (
                {
                    TITLE: records.call_title(state.lead_label, state.started),
                    "Session ID": session_id,
                    "Mode": mode,
                    "Outcome": "in progress",
                    "Started": state.started,
                    "Lead": [state.lead_page] if state.lead_page else None,
                },
                records.call_body(mode),
            ),
        )

    def _lead_page_for(self, session_id: str | None, lead_id: str | None) -> str | None:
        state = self._session(session_id)
        if state.lead_page:
            return state.lead_page
        if not lead_id:
            return None
        key = zuno_id("lead", lead_id)
        cached = self._ids.get(key)
        if cached:
            return cached
        page = self._client.find_by_zuno_id(self._ds["leads"], key)
        if page is None:
            return None
        self._ids[key] = page["id"]
        return page["id"]

    # --- handlers --------------------------------------------------------

    def on_lead_upserted(self, payload: dict[str, Any]) -> None:
        lead = payload.get("lead") or {}
        if not lead:
            return
        sid, mode = payload.get("session_id"), payload.get("mode")
        state = self._session(sid)
        result = self._upsert(
            "leads",
            records.lead_key(lead, sid),
            records.lead_values(lead, mode, sid),
            on_create={"Stage": "New"},
            children=records.lead_body(mode),
        )
        first_link = state.lead_page != result.page_id
        state.lead_page = result.page_id
        state.lead_label = records.lead_label(lead) or state.lead_label
        if not sid:
            return

        call = self._call_page(sid, mode)
        if first_link or state.call_label != state.lead_label:
            self._upsert(
                "calls",
                records.call_key(sid),
                {TITLE: records.call_title(state.lead_label, state.started), "Lead": [result.page_id]},
            )
            state.call_label = state.lead_label
        if state.products:
            self._add_relation(result.page_id, "Products of interest", state.products)
        orphans, state.orphan_objections = state.orphan_objections, []
        for objection_page in orphans:
            self._client.set_relation(objection_page, "Lead", [result.page_id])
        logger.debug("Notion mirror: lead %s on call %s", result.page_id, call)

    def on_product_spotlighted(self, payload: dict[str, Any]) -> None:
        product = payload.get("product") or {}
        sid, mode = payload.get("session_id"), payload.get("mode")
        if not sid:
            return
        page = self._product_page(product, mode=mode)
        if not page:
            return
        state = self._session(sid)
        if page not in state.products:
            state.products.append(page)
        state.last_product = page
        self._add_relation(self._call_page(sid, mode), "Products mentioned", [page])
        if state.lead_page:
            self._add_relation(state.lead_page, "Products of interest", [page])

    def on_objection_logged(self, payload: dict[str, Any]) -> None:
        objection = payload.get("objection") or {}
        sid, mode = payload.get("session_id"), payload.get("mode")
        if not objection or not sid:
            return
        state = self._session(sid)
        topic = str(objection.get("topic") or "other")
        playbook = self._ensure(
            "playbook",
            zuno_id("playbook", topic),
            lambda: (records.playbook_values(topic), records.playbook_body(topic)),
        )
        call = self._call_page(sid, mode)

        explicit = objection.get("product_ids") or objection.get("products") or payload.get("products") or []
        if isinstance(explicit, (str, dict)):
            explicit = [explicit]
        products: list[str] = []
        for item in explicit:
            if isinstance(item, dict):
                page = self._product_page(item, mode=mode)
            else:
                page = self._product_page(product_id=str(item), mode=mode)
            if page:
                products.append(page)
        # Nothing named: the product on screen when it was raised is the best
        # available guess at what the objection was about.
        if not products and state.last_product:
            products = [state.last_product]

        lead = state.lead_page
        key = records.objection_key(sid, objection)
        result = self._upsert(
            "objections",
            key,
            {
                **records.objection_values(objection, mode),
                "Call": [call],
                "Lead": [lead] if lead else None,
                "Playbook": [playbook],
            },
            children=records.objection_body(objection),
        )
        if not lead and result.created:
            state.orphan_objections.append(result.page_id)
        if products:
            self._add_relation(result.page_id, "Products", products)

        if objection.get("resolved") and key not in self._resolved:
            self._resolved.add(key)
            previous = ((result.previous or {}).get("properties") or {}).get("Status") or {}
            was = (previous.get("status") or previous.get("select") or {}).get("name")
            if was != "Resolved":
                self._client.append_children(playbook, [_answer_line(objection, topic, products)])

    def on_meeting_booked(self, payload: dict[str, Any]) -> None:
        booking = payload.get("booking") or {}
        sid, mode = payload.get("session_id") or booking.get("session_id"), payload.get("mode")
        if not booking or not sid:
            return
        state = self._session(sid)
        lead = self._lead_page_for(sid, booking.get("lead_id"))
        who = state.lead_label or booking.get("lead_name") or booking.get("contact")
        call = self._call_page(sid, mode)
        self._upsert(
            "meetings",
            records.meeting_key(booking, sid),
            {
                **records.meeting_values(booking, mode, who),
                "Lead": [lead] if lead else None,
                "Call": [call],
            },
            children=records.meeting_body(booking, who),
        )

    def on_mode_changed(self, payload: dict[str, Any]) -> None:
        sid, mode = payload.get("session_id"), payload.get("mode")
        if not mode or not sid:
            return
        state = self._session(sid)
        call = self._call_page(sid, mode)
        self._upsert("calls", records.call_key(sid), {"Mode": mode})
        previous, by = payload.get("previous"), payload.get("by")
        line = f"Switched to {mode} mode" + (f" from {previous}" if previous else "") + (f" ({by})" if by else "") + "."
        self._client.append_children(call, [blocks.paragraph(blocks.text(line))])
        if state.lead_page:
            self._client.update_page(state.lead_page, self._props("leads", {"Mode": mode}))

    def on_call_ended(self, payload: dict[str, Any]) -> None:
        sid, mode = payload.get("session_id"), payload.get("mode")
        if not sid:
            return
        summary = payload.get("summary") or {}
        outcome = payload.get("outcome")
        state = self._session(sid)

        products = list(state.products)
        for product_id in payload.get("products") or []:
            page = self._product_page(product_id=str(product_id), mode=mode)
            if page and page not in products:
                products.append(page)

        lead = self._lead_page_for(sid, summary.get("lead_id"))
        if lead is None and (summary.get("contact") or summary.get("company")):
            # The caller was never written as a lead (no lead_upserted reached
            # us), but the wrap-up knows who it was: keep the call attached to
            # someone rather than floating as an isolated node.
            fallback = {"id": summary.get("lead_id"), "name": summary.get("contact"), "company": summary.get("company")}
            lead = self._upsert(
                "leads",
                records.lead_key(fallback, sid),
                {TITLE: records.lead_label(fallback), "Company": summary.get("company"), "Mode": mode},
                on_create={"Stage": "New"},
                children=records.lead_body(mode),
            ).page_id
            state.lead_page = lead
            state.lead_label = records.lead_label(fallback)

        call = self._call_page(sid, mode)
        values = records.call_summary_values(summary, outcome, mode)
        if state.lead_label:
            values[TITLE] = records.call_title(state.lead_label, state.started)
        if lead:
            values["Lead"] = [lead]
        self._upsert("calls", records.call_key(sid), values)
        if products:
            self._add_relation(call, "Products mentioned", products)
            if lead:
                self._add_relation(lead, "Products of interest", products)
        if not state.wrapped:
            state.wrapped = True
            self._client.append_children(call, records.call_summary_body(summary, outcome))


def _answer_line(objection: dict, topic: str, products: list[str]) -> dict:
    answer = " ".join(str(objection.get("resolution_text") or "").split())
    parts: list[list[dict]] = []
    if answer:
        parts.append(blocks.text(f"“{answer[:1500]}” ", bold=True))
        parts.append(blocks.text(f"resolved a {topic} objection"))
    else:
        parts.append(blocks.text(f"Resolved a {topic} objection"))
    if products:
        parts.append(blocks.text(" about "))
        for index, page in enumerate(products[:5]):
            if index:
                parts.append(blocks.text(", "))
            parts.append(blocks.mention(page))
    parts.append(blocks.text("."))
    return blocks.paragraph(*parts)


_mirror: NotionMirror | None = None


def register() -> None:
    """Subscribe the mirror to the bus, or do nothing if it is not set up."""
    global _mirror
    from app.integrations import bus

    settings = load_notion_settings()
    missing = settings.missing()
    if missing:
        what = "NOTION_TOKEN" if "NOTION_TOKEN" in missing else ", ".join(missing)
        logger.info("Notion mirror off: %s not set (scripts/setup_notion.py sets it up)", what)
        return
    client = NotionClient(
        settings.notion_token, version=settings.notion_version, max_rps=settings.notion_max_rps
    )
    mirror = NotionMirror(client, settings.data_source_ids())
    for event, handler in mirror.handlers().items():
        bus.subscribe(event, handler)
    _mirror = mirror
    logger.info("Notion mirror on: syncing calls, leads and objections to Notion (API %s)", settings.notion_version)
