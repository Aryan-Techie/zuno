"""The Notion databases ZUNO mirrors into, and how values are written to them.

Shaped by what Graphify draws (docs/notion.md has the sources): every page and
every database row is a node, and the only edges are @-mentions, "link to
page" and relation properties. Parent/child nesting draws nothing, and a
database itself is a filter, not a node. So anything that should show up as a
line in the graph is a relation property here, two-way so both pages list
each other in Notion as well.

Every database has a "ZUNO ID" text property holding a stable key such as
"product:dior-sauvage-eau-de-parfum" or "call:<session id>". Upserts look rows
up by it, which is what makes re-running the setup or replaying an event safe.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

TITLE = "Name"
ZUNO_ID = "ZUNO ID"

# Notion caps one rich text item at 2,000 characters and an array at 100 items.
_TEXT_LIMIT = 2000
_ARRAY_LIMIT = 100


@dataclass(frozen=True)
class Option:
    name: str
    color: str = "default"
    # Status options only: "To-do", "In progress" or "Complete".
    group: str | None = None


@dataclass(frozen=True)
class Prop:
    name: str
    kind: str
    options: tuple[Option, ...] = ()
    # Relations only: the database key it points at, and the name the
    # matching property gets on that side.
    target: str | None = None
    reverse: str | None = None
    number_format: str | None = None


@dataclass(frozen=True)
class DatabaseSpec:
    key: str
    title: str
    icon: str
    description: str
    props: tuple[Prop, ...] = field(default_factory=tuple)

    def prop(self, name: str) -> Prop:
        for prop in self.props:
            if prop.name == name:
                return prop
        raise KeyError(f"{self.key} has no property {name!r}")


def _title() -> Prop:
    return Prop(TITLE, "title")


def _zuno_id() -> Prop:
    return Prop(ZUNO_ID, "rich_text")


_MODE = Prop(
    "Mode", "select", (Option("apple", "gray"), Option("perfume", "pink"))
)

LEAD_STAGES = {
    "new": "New",
    "qualified": "Qualified",
    "meeting_booked": "Meeting booked",
    "escalated": "Escalated",
    "disqualified": "Disqualified",
}

OBJECTION_TOPICS = ("pricing", "trust", "product")

# Listed in creation order: a relation can only point at a database that
# already exists, so every target comes before the databases pointing at it.
DATABASES: tuple[DatabaseSpec, ...] = (
    DatabaseSpec(
        "brands",
        "Brands",
        "🏷️",
        "The houses ZUNO sells. Each brand links to every product it makes.",
        (
            _title(),
            _zuno_id(),
            _MODE,
            Prop("Website", "url"),
            Prop("About", "rich_text"),
        ),
    ),
    DatabaseSpec(
        "families",
        "Olfactory Families",
        "🌿",
        "Fragrance families. Fragrances that share a family cluster around it.",
        (_title(), _zuno_id()),
    ),
    DatabaseSpec(
        "notes",
        "Fragrance Notes",
        "💧",
        "Ingredients named in fragrance pyramids, linked to each fragrance by tier.",
        (
            _title(),
            _zuno_id(),
            Prop(
                "Tiers",
                "multi_select",
                (Option("top", "yellow"), Option("heart", "pink"), Option("base", "brown")),
            ),
        ),
    ),
    DatabaseSpec(
        "playbook",
        "Objection Playbook",
        "📘",
        "One page per objection type. Answers that resolved one are added to it.",
        (
            _title(),
            _zuno_id(),
            Prop(
                "Topic",
                "select",
                (Option("pricing", "orange"), Option("trust", "purple"), Option("product", "blue")),
            ),
            Prop("Guidance", "rich_text"),
        ),
    ),
    DatabaseSpec(
        "products",
        "Products",
        "🛍️",
        "The Apple and Dior catalogs, linked to brand, families and notes.",
        (
            _title(),
            _zuno_id(),
            Prop("Brand", "relation", target="brands", reverse="Products"),
            Prop("Families", "relation", target="families", reverse="Products"),
            Prop("Top notes", "relation", target="notes", reverse="Top note in"),
            Prop("Heart notes", "relation", target="notes", reverse="Heart note in"),
            Prop("Base notes", "relation", target="notes", reverse="Base note in"),
            _MODE,
            Prop("Category", "select"),
            Prop("Line", "select"),
            Prop("Gender", "select"),
            Prop("Subcategory", "rich_text"),
            Prop("Price from", "number", number_format="number_with_commas"),
            Prop("Currency", "select", (Option("HKD", "red"), Option("USD", "green"))),
            Prop("Sizes", "rich_text"),
            Prop("Stock", "number"),
            Prop("Product page", "url"),
            Prop("Image", "url"),
            Prop("Description", "rich_text"),
        ),
    ),
    DatabaseSpec(
        "leads",
        "Leads",
        "👤",
        "Everyone ZUNO has spoken to, linked to the products they asked about.",
        (
            _title(),
            _zuno_id(),
            # A Notion Status property, not a select: Graphify can colour and
            # filter nodes by status, and only by that property type.
            Prop(
                "Stage",
                "status",
                (
                    Option("New", "gray", "To-do"),
                    Option("Qualified", "blue", "In progress"),
                    Option("Meeting booked", "green", "In progress"),
                    Option("Escalated", "orange", "In progress"),
                    Option("Disqualified", "red", "Complete"),
                ),
            ),
            Prop("Products of interest", "relation", target="products", reverse="Interested leads"),
            _MODE,
            Prop("Company", "rich_text"),
            Prop("Role", "rich_text"),
            Prop("Industry", "rich_text"),
            Prop("Email", "email"),
            Prop("Phone", "phone_number"),
            Prop("Seats", "number"),
            Prop("Budget", "rich_text"),
            Prop("Timeline", "rich_text"),
            Prop("Decision stage", "select"),
            Prop("Pain points", "rich_text"),
            Prop("Outcome", "rich_text"),
        ),
    ),
    DatabaseSpec(
        "calls",
        "Calls",
        "📞",
        "One page per ZUNO call: who, which products came up, how it ended.",
        (
            _title(),
            _zuno_id(),
            Prop("Lead", "relation", target="leads", reverse="Calls"),
            Prop("Products mentioned", "relation", target="products", reverse="Mentioned on calls"),
            _MODE,
            Prop("Outcome", "select"),
            Prop("Headline", "rich_text"),
            Prop("Next step", "rich_text"),
            Prop("Urgency", "select"),
            Prop("Duration (s)", "number"),
            Prop("Started", "date"),
            Prop("Session ID", "rich_text"),
        ),
    ),
    DatabaseSpec(
        "objections",
        "Objections",
        "🛑",
        "Objections raised on calls, linked to the call, the lead, the product and the playbook.",
        (
            _title(),
            _zuno_id(),
            Prop(
                "Status",
                "status",
                (Option("Open", "red", "To-do"), Option("Resolved", "green", "Complete")),
            ),
            Prop("Call", "relation", target="calls", reverse="Objections"),
            Prop("Lead", "relation", target="leads", reverse="Objections"),
            Prop("Products", "relation", target="products", reverse="Objections"),
            Prop("Playbook", "relation", target="playbook", reverse="Objections"),
            Prop(
                "Topic",
                "select",
                (Option("pricing", "orange"), Option("trust", "purple"), Option("product", "blue")),
            ),
            Prop("Customer said", "rich_text"),
            Prop("Answer", "rich_text"),
            Prop("Attempts", "number"),
            _MODE,
        ),
    ),
    DatabaseSpec(
        "meetings",
        "Meetings",
        "📅",
        "Follow-up meetings ZUNO booked, linked to the lead and the call that booked them.",
        (
            _title(),
            _zuno_id(),
            Prop("Lead", "relation", target="leads", reverse="Meetings"),
            Prop("Call", "relation", target="calls", reverse="Meetings"),
            Prop("When", "date"),
            Prop("Rep", "rich_text"),
            Prop(
                "Status", "select", (Option("booked", "green"), Option("cancelled", "red"))
            ),
            _MODE,
        ),
    ),
)

SPECS: dict[str, DatabaseSpec] = {spec.key: spec for spec in DATABASES}


# --- schema payloads -------------------------------------------------------


def property_schema(prop: Prop, data_source_ids: dict[str, str], *, status_as_select: bool = False) -> dict:
    """The create/update-data-source schema for one property."""
    kind = prop.kind
    if kind == "status" and status_as_select:
        kind = "select"
    if kind == "relation":
        target = data_source_ids.get(prop.target or "")
        if not target:
            raise ValueError(f"relation {prop.name!r} needs the {prop.target} data source first")
        return {
            "relation": {"data_source_id": target, "type": "dual_property", "dual_property": {}}
        }
    if kind in ("select", "multi_select"):
        return {kind: {"options": [{"name": o.name, "color": o.color} for o in prop.options]}}
    if kind == "status":
        return {
            "status": {
                "options": [
                    {"name": o.name, "color": o.color, **({"group": o.group} if o.group else {})}
                    for o in prop.options
                ]
            }
        }
    if kind == "number":
        return {"number": {"format": prop.number_format or "number"}}
    return {kind: {}}


def database_properties(
    spec: DatabaseSpec, data_source_ids: dict[str, str], *, status_as_select: bool = False
) -> dict[str, dict]:
    return {
        prop.name: property_schema(prop, data_source_ids, status_as_select=status_as_select)
        for prop in spec.props
    }


# --- ids -------------------------------------------------------------------


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "x"


def zuno_id(kind: str, *parts: str) -> str:
    return ":".join([kind, *(str(p) for p in parts)])


# --- value encoders --------------------------------------------------------


def text_items(value: str | None) -> list[dict]:
    """Plain text as rich text items, split to stay under Notion's limits."""
    if not value:
        return []
    chunks = [value[i : i + _TEXT_LIMIT] for i in range(0, len(value), _TEXT_LIMIT)]
    return [{"type": "text", "text": {"content": chunk}} for chunk in chunks[:_ARRAY_LIMIT]]


def option_name(value: Any) -> str:
    # Select option names may not contain commas, and are capped at 100 chars.
    return str(value).replace(",", " ").strip()[:100]


def _date_value(value: Any) -> dict | None:
    if not value:
        return None
    if isinstance(value, dict):
        start = value.get("start")
        if not start:
            return None
        out = {"start": _iso(start)}
        if value.get("end"):
            out["end"] = _iso(value["end"])
        return out
    return {"start": _iso(value)}


def _iso(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def encode(kind: str, value: Any) -> dict:
    """One property value in the shape Notion's page endpoints take."""
    if kind == "title":
        return {"title": text_items(str(value) if value is not None else "")}
    if kind == "rich_text":
        return {"rich_text": text_items(str(value) if value is not None else "")}
    if kind == "number":
        return {"number": value}
    if kind == "select":
        return {"select": {"name": option_name(value)} if value else None}
    if kind == "status":
        return {"status": {"name": option_name(value)} if value else None}
    if kind == "multi_select":
        names = []
        for item in value or []:
            name = option_name(item)
            if name and name not in names:
                names.append(name)
        return {"multi_select": [{"name": n} for n in names[:_ARRAY_LIMIT]]}
    if kind == "date":
        return {"date": _date_value(value)}
    if kind in ("url", "email", "phone_number"):
        return {kind: str(value) if value else None}
    if kind == "checkbox":
        return {"checkbox": bool(value)}
    if kind == "relation":
        ids = list(dict.fromkeys(value or []))
        return {"relation": [{"id": page_id} for page_id in ids[:_ARRAY_LIMIT]]}
    raise ValueError(f"no encoder for property kind {kind!r}")


def build_properties(
    key: str, values: dict[str, Any], kinds: dict[str, str] | None = None
) -> dict[str, dict]:
    """Encode `values` (property name -> plain value) for database `key`.

    None means "unknown, leave what is there", not "clear it": events carry
    partial records, and a lead_upserted without an email must not wipe the
    email an earlier one wrote. `kinds` overrides the declared type from the
    live schema, for a Status property that had to be created as a select.
    """
    spec = SPECS[key]
    out: dict[str, dict] = {}
    for name, value in values.items():
        if value is None:
            continue
        kind = (kinds or {}).get(name) or spec.prop(name).kind
        out[name] = encode(kind, value)
    return out


def relation_props(key: str) -> Iterable[Prop]:
    return (prop for prop in SPECS[key].props if prop.kind == "relation")
