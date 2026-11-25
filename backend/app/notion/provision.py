"""One-shot workspace setup behind scripts/setup_notion.py.

Creates the ZUNO databases under a parent page, seeds the catalog (brands,
families, notes, products, playbook pages), writes a "Start here" hub page,
and records the resulting ids in backend/.env. Every step finds what a
previous run made before creating anything, so the script is safe to re-run:
after a crash halfway, after a schema change here (missing properties are
added), or just to refresh the catalog.

Lookups, in order: the data source id already in backend/.env, then a
database with the expected title directly under the parent page, then create.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.notion import blocks, records
from app.notion.catalog import SeedPlan, brand_key, family_key, family_names, note_key, note_names
from app.notion.client import NotionClient, NotionError, is_trashed, plain_text
from app.notion.config import DATA_SOURCE_ENV
from app.notion.schema import (
    DATABASES,
    SPECS,
    TITLE,
    ZUNO_ID,
    DatabaseSpec,
    build_properties,
    database_properties,
    property_schema,
)

START_TITLE = "Start here"
GRAPHIFY_URL = "https://www.getgraphify.com"
GRAPHIFY_FREE_PAGE_LIMIT = 100

_UUID_RE = re.compile(r"([0-9a-f]{8})-?([0-9a-f]{4})-?([0-9a-f]{4})-?([0-9a-f]{4})-?([0-9a-f]{12})", re.I)


def parse_page_id(value: str) -> str:
    """A Notion page id from an id (with or without dashes) or a page URL
    such as https://www.notion.so/team/ZUNO-1f2e...?pvs=4."""
    raw = (value or "").strip()
    if not raw:
        raise ValueError("no Notion page id or URL given")
    path = re.split(r"[?#]", raw, maxsplit=1)[0]
    matches = list(_UUID_RE.finditer(path))
    if not matches:
        raise ValueError("could not find a 32-character Notion page id in that value")
    return "-".join(matches[-1].groups()).lower()


@dataclass
class DatabaseRef:
    key: str
    database_id: str
    data_source_id: str
    created: bool = False
    schema: dict[str, dict] = field(default_factory=dict)


@dataclass
class SetupResult:
    databases: dict[str, DatabaseRef]
    start_page_id: str | None = None
    seeded: dict[str, dict[str, int]] = field(default_factory=dict)

    def env_values(self, token: str, parent_page_id: str) -> dict[str, str]:
        values = {"NOTION_TOKEN": token, "NOTION_PARENT_PAGE_ID": parent_page_id}
        if self.start_page_id:
            values["NOTION_START_PAGE_ID"] = self.start_page_id
        for key, ref in self.databases.items():
            values[DATA_SOURCE_ENV[key]] = ref.data_source_id
        return values


class Provisioner:
    def __init__(
        self, client: NotionClient, parent_page_id: str, *, log: Callable[[str], None] = print
    ) -> None:
        self.client = client
        self.parent = parent_page_id
        self.log = log
        self._children: list[dict] | None = None
        # ZUNO ID -> page id for every row the last seed() wrote or found.
        self.seeded_ids: dict[str, str] = {}

    def _parent_children(self, refresh: bool = False) -> list[dict]:
        if self._children is None or refresh:
            self._children = self.client.list_children(self.parent)
        return self._children

    # --- databases -------------------------------------------------------

    def ensure_databases(self, known: dict[str, str] | None = None) -> dict[str, DatabaseRef]:
        known = known or {}
        refs: dict[str, DatabaseRef] = {}
        for spec in DATABASES:
            ref = self._find(spec, known.get(spec.key))
            if ref is None:
                ref = self._create(spec, refs)
                self.log(f"  created   {spec.title}")
            else:
                added = self._add_missing(spec, ref, refs)
                note = f" (added {', '.join(added)})" if added else ""
                self.log(f"  found     {spec.title}{note}")
            refs[spec.key] = ref
        self._name_reverse_relations(refs)
        return refs

    def _ref_from_data_source(self, key: str, data_source: dict, created: bool = False) -> DatabaseRef:
        parent = data_source.get("parent") or {}
        database_id = parent.get("database_id") or ""
        return DatabaseRef(key, database_id, data_source["id"], created, data_source.get("properties") or {})

    def _find(self, spec: DatabaseSpec, data_source_id: str | None) -> DatabaseRef | None:
        if data_source_id:
            try:
                data_source = self.client.retrieve_data_source(data_source_id)
                if not is_trashed(data_source):
                    return self._ref_from_data_source(spec.key, data_source)
            except NotionError as exc:
                if exc.status not in (400, 403, 404):
                    raise
        for block in self._parent_children():
            if block.get("type") != "child_database" or is_trashed(block):
                continue
            if (block.get("child_database") or {}).get("title") != spec.title:
                continue
            database = self.client.retrieve_database(block["id"])
            sources = database.get("data_sources") or []
            if is_trashed(database) or not sources:
                continue
            data_source = self.client.retrieve_data_source(sources[0]["id"])
            ref = self._ref_from_data_source(spec.key, data_source)
            ref.database_id = ref.database_id or database["id"]
            return ref
        return None

    def _create(self, spec: DatabaseSpec, refs: dict[str, DatabaseRef]) -> DatabaseRef:
        ds_ids = {k: r.data_source_id for k, r in refs.items()}
        has_status = any(p.kind == "status" for p in spec.props)
        try:
            database = self.client.create_database(
                self.parent, spec.title, database_properties(spec, ds_ids), icon=spec.icon, description=spec.description
            )
        except NotionError as exc:
            if exc.status != 400 or not has_status:
                raise
            # Status options with groups are newer API surface than the rest
            # of this schema. A workspace that rejects them still gets the
            # same values as a select, which the mirror detects and writes
            # in that shape; Graphify just cannot colour by it.
            self.log(f"  note      {spec.title}: Status property rejected ({exc.message}); using a select")
            database = self.client.create_database(
                self.parent,
                spec.title,
                database_properties(spec, ds_ids, status_as_select=True),
                icon=spec.icon,
                description=spec.description,
            )
        data_source = self.client.retrieve_data_source(database["data_sources"][0]["id"])
        ref = self._ref_from_data_source(spec.key, data_source, created=True)
        ref.database_id = ref.database_id or database["id"]
        return ref

    def _add_missing(self, spec: DatabaseSpec, ref: DatabaseRef, refs: dict[str, DatabaseRef]) -> list[str]:
        ds_ids = {k: r.data_source_id for k, r in refs.items()}
        changes: dict[str, dict] = {}
        title_name = next((n for n, p in ref.schema.items() if p.get("type") == "title"), None)
        if title_name and title_name != TITLE and TITLE not in ref.schema:
            changes[title_name] = {"name": TITLE}
        missing = [p for p in spec.props if p.kind != "title" and p.name not in ref.schema]
        for prop in missing:
            changes[prop.name] = property_schema(prop, ds_ids)
        if not changes:
            return []
        try:
            data_source = self.client.update_data_source(ref.data_source_id, changes)
        except NotionError as exc:
            if exc.status != 400 or not any(p.kind == "status" for p in missing):
                raise
            for prop in missing:
                if prop.kind == "status":
                    changes[prop.name] = property_schema(prop, ds_ids, status_as_select=True)
            data_source = self.client.update_data_source(ref.data_source_id, changes)
        ref.schema = data_source.get("properties") or self.client.retrieve_data_source(ref.data_source_id).get(
            "properties", {}
        )
        return [p.name for p in missing]

    def _name_reverse_relations(self, refs: dict[str, DatabaseRef]) -> None:
        """Give the auto-created far side of each two-way relation a readable
        name ("Products" on a brand, not "Related to Products (Brand)").
        Cosmetic for Notion readers; Graphify draws the edge either way."""
        for ref in refs.values():
            ref.schema = self.client.retrieve_data_source(ref.data_source_id).get("properties") or ref.schema
        for spec in DATABASES:
            source = refs[spec.key]
            for prop in spec.props:
                if prop.kind != "relation" or not prop.reverse:
                    continue
                relation = (source.schema.get(prop.name) or {}).get("relation") or {}
                dual = relation.get("dual_property") or {}
                synced_name = dual.get("synced_property_name")
                synced_id = dual.get("synced_property_id") or synced_name
                target = refs[prop.target or ""]
                if not synced_name or synced_name == prop.reverse or prop.reverse in target.schema:
                    continue
                try:
                    data_source = self.client.update_data_source(
                        target.data_source_id, {synced_id: {"name": prop.reverse}}
                    )
                    target.schema = data_source.get("properties") or target.schema
                    if synced_name in target.schema:
                        target.schema[prop.reverse] = target.schema.pop(synced_name)
                except NotionError as exc:
                    self.log(f"  note      could not rename {synced_name!r} on {SPECS[target.key].title}: {exc.message}")

    # --- seed ------------------------------------------------------------

    def seed(self, refs: dict[str, DatabaseRef], plan: SeedPlan, *, update_existing: bool = True) -> dict[str, dict[str, int]]:
        ids: dict[str, str] = {}
        stats: dict[str, dict[str, int]] = {}

        def put(db: str, key: str, values: dict[str, Any], children: list[dict], index: dict[str, str]) -> None:
            counts = stats.setdefault(db, {"created": 0, "updated": 0, "skipped": 0})
            props = build_properties(db, {**values, ZUNO_ID: key})
            if key in index:
                ids[key] = index[key]
                if update_existing:
                    self.client.update_page(index[key], props)
                    counts["updated"] += 1
                else:
                    counts["skipped"] += 1
                return
            page = self.client.create_page(refs[db].data_source_id, props, children=children)
            ids[key] = index[key] = page["id"]
            counts["created"] += 1

        index = self.client.zuno_index(refs["brands"].data_source_id)
        for key, brand in plan.brands.items():
            put("brands", key, records.brand_values(brand["name"], brand["mode"]), records.brand_body(brand["name"]), index)

        index = self.client.zuno_index(refs["families"].data_source_id)
        for key, family in plan.families.items():
            put("families", key, records.family_values(family["name"]), records.family_body(family["name"]), index)

        index = self.client.zuno_index(refs["notes"].data_source_id)
        for key, note in plan.notes.items():
            put("notes", key, records.note_values(note["name"], note["tiers"]), records.note_body(note["name"]), index)

        index = self.client.zuno_index(refs["playbook"].data_source_id)
        for key, entry in plan.playbook.items():
            topic = entry["topic"]
            put("playbook", key, records.playbook_values(topic), records.playbook_body(topic), index)

        index = self.client.zuno_index(refs["products"].data_source_id)
        for product in plan.products:
            mode = product["_mode"]
            notes = {
                tier: [ids[note_key(n)] for n in names if note_key(n) in ids]
                for tier, names in note_names(product).items()
            }
            values = records.product_values(
                product,
                mode,
                brand=ids.get(brand_key(product) or ""),
                families=[ids[family_key(n)] for n in family_names(product) if family_key(n) in ids],
                notes=notes,
            )
            put("products", f"product:{product['id']}", values, records.product_body(product), index)

        self.seeded_ids = ids
        return stats

    # --- hub page --------------------------------------------------------

    def ensure_start_page(
        self,
        refs: dict[str, DatabaseRef],
        hubs: dict[str, list[tuple[str, str]]],
        *,
        known_id: str | None = None,
        rebuild: bool = False,
    ) -> str:
        page_id: str | None = None
        if known_id:
            try:
                page = self.client.retrieve_page(known_id)
                if not is_trashed(page):
                    page_id = page["id"]
            except NotionError as exc:
                if exc.status not in (400, 403, 404):
                    raise
        if page_id is None:
            for block in self._parent_children(refresh=True):
                if block.get("type") == "child_page" and not is_trashed(block):
                    if (block.get("child_page") or {}).get("title") == START_TITLE:
                        page_id = block["id"]
                        break

        if page_id is None:
            page_id = self._write_start(None, refs, hubs)
            self.log(f"  created   {START_TITLE}")
        else:
            existing = self.client.list_children(page_id)
            if rebuild:
                for block in existing:
                    self.client.delete_block(block["id"])
            if rebuild or not existing:
                self._write_start(page_id, refs, hubs)
                self.log(f"  rewrote   {START_TITLE}")
            else:
                self.log(f"  found     {START_TITLE} (left as is; --rebuild-start-page rewrites it)")

        # A link from the ZUNO page itself, so the parent is not an isolated
        # node and the whole workspace hangs together from the top.
        linked = any(
            block.get("type") == "link_to_page"
            and (block.get("link_to_page") or {}).get("page_id", "").replace("-", "") == page_id.replace("-", "")
            for block in self._parent_children(refresh=True)
        )
        if not linked:
            self.client.append_children(self.parent, [blocks.link_to_page(page_id)])
        return page_id

    def _write_start(
        self, page_id: str | None, refs: dict[str, DatabaseRef], hubs: dict[str, list[tuple[str, str]]]
    ) -> str:
        """Create (page_id None) or fill the hub page. A "link to page" block
        pointing at a database is the least-used block shape here; if the
        API refuses it, the same links go in as plain text links instead
        rather than failing the last step of an otherwise finished setup."""
        for database_links in ("block", "text"):
            content = start_page_blocks(refs, hubs, database_links=database_links)
            try:
                if page_id is None:
                    return self.client.create_child_page(self.parent, START_TITLE, children=content, icon="🧭")["id"]
                self.client.append_children(page_id, content)
                return page_id
            except NotionError as exc:
                if exc.status != 400 or database_links == "text":
                    raise
                self.log(f"  note      database link blocks refused ({exc.message}); using text links")
        raise AssertionError("unreachable")  # pragma: no cover

    def hub_pages(self, refs: dict[str, DatabaseRef]) -> dict[str, list[tuple[str, str]]]:
        """Brand and playbook pages, for the Start here page to link."""
        out: dict[str, list[tuple[str, str]]] = {}
        for key in ("brands", "playbook"):
            out[key] = [
                (page["id"], plain_text(page.get("properties", {}).get(TITLE)) or "Untitled")
                for page in self.client.query_data_source(refs[key].data_source_id)
            ]
        return out


def start_page_blocks(
    refs: dict[str, DatabaseRef],
    hubs: dict[str, list[tuple[str, str]]],
    *,
    database_links: str = "block",
) -> list[dict]:
    """Top-level blocks only: Graphify follows nested blocks to a limited
    depth, so a link inside a toggle could be missed. Brand and playbook
    pages get "link to page" blocks, which Graphify draws as edges; the
    databases are linked for people (a database is not a graph node)."""
    body: list[dict] = [
        blocks.callout(
            "Written by ZUNO, the voice sales agent, and kept current while it takes calls. "
            "Edit freely, but keep the ZUNO ID column: ZUNO finds its rows by it.",
            "🤖",
        ),
        blocks.paragraph(
            blocks.text(
                "Every call ZUNO takes lands here: the lead, the products they asked about, the "
                "objections they raised and the meeting that came out of it, all linked to the "
                "catalog. Relations are the links, so the workspace reads as a graph."
            )
        ),
        blocks.heading("How it connects", 2),
        blocks.bullet(blocks.text("Products link to their Brand, Olfactory Families and Top, Heart and Base notes.")),
        blocks.bullet(blocks.text("Leads link to the Products they asked about; Calls link to the Lead and the Products mentioned.")),
        blocks.bullet(blocks.text("Objections link to the Call, the Lead, the Product and their Playbook page.")),
        blocks.bullet(blocks.text("Playbook pages @-mention the products an answer worked for. Meetings link to the Lead and the Call.")),
    ]
    if hubs.get("brands"):
        body.append(blocks.heading("Brands", 2))
        body.extend(blocks.link_to_page(page_id) for page_id, _ in hubs["brands"])
    if hubs.get("playbook"):
        body.append(blocks.heading("Objection playbook", 2))
        body.extend(blocks.link_to_page(page_id) for page_id, _ in hubs["playbook"])
    body.append(blocks.heading("Databases", 2))
    for spec in DATABASES:
        ref = refs.get(spec.key)
        if not (ref and ref.database_id):
            continue
        if database_links == "block":
            body.append(blocks.link_to_database(ref.database_id))
            body.append(blocks.paragraph(blocks.text(spec.description)))
        else:
            url = f"https://www.notion.so/{ref.database_id.replace('-', '')}"
            body.append(blocks.bullet(blocks.text(spec.title, url=url, bold=True), blocks.text(f": {spec.description}")))
    body.append(blocks.heading("See it as a graph", 2))
    body.append(
        blocks.paragraph(
            blocks.text("Open "),
            blocks.text("Graphify", url=GRAPHIFY_URL),
            blocks.text(
                ", connect this Notion workspace and give it access to the ZUNO page. "
                "Everything under it comes along, and new rows appear on the next sync."
            ),
        )
    )
    return body


# --- backend/.env ----------------------------------------------------------


def write_env(path: Path, values: dict[str, str]) -> None:
    """Set NOTION_* keys in an env file, keeping every other line, the
    comments, and the file's line endings (backend/.env is CRLF).

    Keys in `values` are replaced where they already are; new ones go after
    the last NOTION_ line, or at the end under a short header. NOTION_* keys
    not in `values` (NOTION_VERSION, NOTION_MAX_RPS) are left alone: those
    are tuning a person chose, not ids this script owns.
    """
    raw = path.read_bytes().decode("utf-8") if path.exists() else ""
    newline = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(newline) if raw else []
    trailing_newline = raw.endswith(newline)
    if trailing_newline:
        lines = lines[:-1]

    pending = dict(values)
    out: list[str] = []
    last_notion = -1
    for line in lines:
        match = re.match(r"\s*(?:export\s+)?(NOTION_[A-Z0-9_]+)\s*=", line)
        if match:
            key = match.group(1)
            if key in values:
                if key in pending:
                    out.append(f"{key}={pending.pop(key)}")
                    last_notion = len(out) - 1
                continue  # a duplicate of a key already written
            last_notion = len(out)
        out.append(line)
    if pending:
        new_lines = [f"{key}={value}" for key, value in pending.items()]
        if last_notion >= 0:
            out[last_notion + 1 : last_notion + 1] = new_lines
        else:
            if out and out[-1].strip():
                out.append("")
            out.append("# Notion mirror for Graphify, written by scripts/setup_notion.py")
            out.extend(new_lines)

    text = newline.join(out) + newline
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(text.encode("utf-8"))
        if path.exists():
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# --- dry run ---------------------------------------------------------------


def estimate_requests(plan: SeedPlan, *, seed: bool = True) -> int:
    relations = sum(1 for spec in DATABASES for p in spec.props if p.kind == "relation")
    setup = 1 + len(DATABASES) * 3 + relations + 6
    rows = plan.page_count() + 5 if seed else 0
    return setup + rows


def describe_plan(plan: SeedPlan, *, seed: bool, max_rps: float, known: dict[str, str]) -> list[str]:
    lines = ["Databases (created in this order under the parent page):"]
    for spec in DATABASES:
        state = "reuse id from env" if known.get(spec.key) else "find by title, else create"
        lines.append(f"  {spec.icon} {spec.title}  [{state}]")
        for prop in spec.props:
            if prop.kind == "relation":
                lines.append(
                    f"      {prop.name} -> {SPECS[prop.target or ''].title} (two-way, far side named {prop.reverse!r})"
                )
            elif prop.kind == "status":
                lines.append(f"      {prop.name}: status [{', '.join(o.name for o in prop.options)}]")
        plain = [p.name for p in spec.props if p.kind not in ("relation", "status")]
        lines.append(f"      also: {', '.join(plain)}")
    lines.append("")
    lines.append(f'Pages: "{START_TITLE}" hub under the parent, linking brands, playbook pages and every database.')
    if seed:
        counts = plan.counts()
        lines.append(
            "Seed: "
            + ", ".join(f"{n} {k}" for k, n in counts.items())
            + f" ({sum(1 for p in plan.products if p['_mode'] == 'apple')} Apple,"
            f" {sum(1 for p in plan.products if p['_mode'] == 'perfume')} perfume)"
        )
    else:
        lines.append("Seed: skipped (--no-seed)")
    pages = (plan.page_count() if seed else 0) + 2
    lines.append(f"Notion pages after setup: about {pages} (ZUNO page + Start here + seeded rows).")
    if pages > GRAPHIFY_FREE_PAGE_LIMIT:
        lines.append(
            f"  Over Graphify's Free web plan ({GRAPHIFY_FREE_PAGE_LIMIT} pages synced). Use Graphify Pro or "
            "Graphify Desktop (no page limit), or re-run with --max-pages 100 to seed a subset that fits."
        )
    requests = estimate_requests(plan, seed=seed)
    lines.append(f"Requests: about {requests}, about {requests / max(max_rps, 0.1) / 60:.1f} min at {max_rps:g} req/s.")
    return lines
