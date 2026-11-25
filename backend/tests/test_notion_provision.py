"""Workspace setup: schema, seed, hub page, env file, dry run."""
import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

from app.notion.catalog import build_seed
from app.notion.config import DATA_SOURCE_ENV
from app.notion.provision import Provisioner, SetupResult, parse_page_id, write_env
from app.notion.schema import DATABASES
from tests.test_notion_fakes import SAMPLE_CATALOGS, FakeNotion

REPO_ROOT = Path(__file__).resolve().parents[2]


def _provision(fake: FakeNotion, known=None):
    prov = Provisioner(fake.client(), fake.parent_page_id, log=lambda _l: None)
    refs = prov.ensure_databases(known or {})
    return prov, refs


# --- page ids ---------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "https://www.notion.so/acme/ZUNO-1f2e3d4c5b6a47988a7b6c5d4e3f2a1b?pvs=4",
        "https://www.notion.so/1f2e3d4c5b6a47988a7b6c5d4e3f2a1b",
        "1f2e3d4c-5b6a-4798-8a7b-6c5d4e3f2a1b",
        "1F2E3D4C5B6A47988A7B6C5D4E3F2A1B",
    ],
)
def test_parse_page_id_accepts_urls_and_ids(value):
    assert parse_page_id(value) == "1f2e3d4c-5b6a-4798-8a7b-6c5d4e3f2a1b"


def test_parse_page_id_rejects_garbage():
    with pytest.raises(ValueError):
        parse_page_id("https://www.notion.so/no-id-here")


# --- env file ---------------------------------------------------------------


def test_write_env_replaces_notion_lines_and_keeps_crlf(tmp_path):
    env = tmp_path / ".env"
    env.write_bytes(
        b"AGORA_APP_ID=abc\r\n# a comment\r\nNOTION_TOKEN=old\r\nNOTION_MAX_RPS=1\r\n"
        b"NOTION_DS_LEADS=stale\r\nOTHER=1\r\nNOTION_TOKEN=dupe\r\n"
    )
    write_env(env, {"NOTION_TOKEN": "new", "NOTION_DS_LEADS": "ds-1", "NOTION_DS_CALLS": "ds-2"})
    raw = env.read_bytes()
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert raw.decode().split("\r\n") == [
        "AGORA_APP_ID=abc",
        "# a comment",
        "NOTION_TOKEN=new",
        "NOTION_MAX_RPS=1",
        "NOTION_DS_LEADS=ds-1",
        "NOTION_DS_CALLS=ds-2",
        "OTHER=1",
        "",
    ]


def test_write_env_appends_block_when_no_notion_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_bytes(b"A=1\r\nB=2\r\n")
    write_env(env, {"NOTION_TOKEN": "t"})
    assert env.read_bytes() == (
        b"A=1\r\nB=2\r\n\r\n# Notion mirror for Graphify, written by scripts/setup_notion.py\r\nNOTION_TOKEN=t\r\n"
    )


# --- seed plan ----------------------------------------------------------------


def test_build_seed_derives_brands_families_and_notes():
    plan = build_seed(SAMPLE_CATALOGS)
    assert set(plan.brands) == {"brand:apple", "brand:dior"}
    # "Floral, Fruity" is two families; "Calabrian bergamot" appears twice in
    # different case and is one note.
    assert set(plan.families) == {"family:fresh-spicy", "family:floral", "family:fruity"}
    assert plan.notes["note:calabrian-bergamot"]["tiers"] == ["top"]
    assert len(plan.notes) == 4
    assert len(plan.products) == 4
    assert set(plan.playbook) == {"playbook:pricing", "playbook:trust", "playbook:product"}


def test_build_seed_respects_page_budget():
    plan = build_seed(SAMPLE_CATALOGS, max_pages=12, reserve_pages=0)
    # 12 minus the ZUNO and Start here pages leaves 10; the 3 playbook pages
    # are always there. Fragrances go first: Sauvage costs 6 (itself, Dior,
    # a family, 3 notes) -> 9. J'adore would cost 4 and the MacBook 2 (it
    # brings the Apple brand), so both are skipped; Rouge Dior costs 1 -> 10.
    assert [p["id"] for p in plan.products] == ["dior-sauvage-eau-de-parfum", "dior-rouge-dior"]
    assert plan.page_count() + 2 == 12


# --- databases ----------------------------------------------------------------


def test_creates_every_database_with_relations_wired():
    fake = FakeNotion()
    _, refs = _provision(fake)
    assert list(refs) == [spec.key for spec in DATABASES]
    assert all(ref.created for ref in refs.values())

    products = fake.data_sources[refs["products"].data_source_id]["properties"]
    assert products["Brand"]["relation"]["data_source_id"] == refs["brands"].data_source_id
    assert products["Top notes"]["relation"]["data_source_id"] == refs["notes"].data_source_id
    objections = fake.data_sources[refs["objections"].data_source_id]["properties"]
    assert objections["Playbook"]["relation"]["data_source_id"] == refs["playbook"].data_source_id
    assert objections["Status"]["type"] == "status"

    # Far sides renamed from Notion's "Related to ..." default.
    leads = fake.data_sources[refs["leads"].data_source_id]["properties"]
    assert {"Calls", "Meetings", "Objections"} <= set(leads)
    brands = fake.data_sources[refs["brands"].data_source_id]["properties"]
    assert "Products" in brands
    assert not any(name.startswith("Related to") for ds in fake.data_sources.values() for name in ds["properties"])


def test_rerun_reuses_databases_by_env_id_and_by_title():
    fake = FakeNotion()
    _, refs = _provision(fake)
    created = fake.count("POST", "/databases")

    _, by_id = _provision(fake, {k: r.data_source_id for k, r in refs.items()})
    _, by_title = _provision(fake)

    assert fake.count("POST", "/databases") == created == len(DATABASES)
    assert {k: r.data_source_id for k, r in by_id.items()} == {k: r.data_source_id for k, r in refs.items()}
    assert {k: r.data_source_id for k, r in by_title.items()} == {k: r.data_source_id for k, r in refs.items()}
    assert not any(r.created for r in by_title.values())


def test_rerun_adds_properties_missing_from_an_older_schema():
    fake = FakeNotion()
    _, refs = _provision(fake)
    del fake.data_sources[refs["calls"].data_source_id]["properties"]["Urgency"]
    _provision(fake)
    assert "Urgency" in fake.data_sources[refs["calls"].data_source_id]["properties"]


def test_status_falls_back_to_select_when_rejected():
    fake = FakeNotion(reject_status=True)
    _, refs = _provision(fake)
    stage = fake.data_sources[refs["leads"].data_source_id]["properties"]["Stage"]
    assert stage["type"] == "select"
    assert [o["name"] for o in stage["select"]["options"]][:2] == ["New", "Qualified"]


# --- seed and hub page --------------------------------------------------------


def test_seed_links_products_and_is_idempotent():
    fake = FakeNotion()
    prov, refs = _provision(fake)
    plan = build_seed(SAMPLE_CATALOGS)

    first = prov.seed(refs, plan)
    assert first["products"]["created"] == 4
    second = prov.seed(refs, plan)
    assert second["products"] == {"created": 0, "updated": 4, "skipped": 0}
    assert len(fake.rows(refs["products"].data_source_id)) == 4
    assert len(fake.rows(refs["notes"].data_source_id)) == 4

    sauvage = fake.row(refs["products"].data_source_id, "product:dior-sauvage-eau-de-parfum")
    dior = fake.row(refs["brands"].data_source_id, "brand:dior")
    bergamot = fake.row(refs["notes"].data_source_id, "note:calabrian-bergamot")
    family = fake.row(refs["families"].data_source_id, "family:fresh-spicy")
    assert fake.relation(sauvage, "Brand") == [dior["id"]]
    assert fake.relation(sauvage, "Top notes") == [bergamot["id"]]
    assert fake.relation(sauvage, "Families") == [family["id"]]
    assert fake.option(sauvage, "Currency") == "HKD"

    jadore = fake.row(refs["products"].data_source_id, "product:dior-jadore-eau-de-parfum")
    assert fake.relation(jadore, "Top notes") == [bergamot["id"]]
    assert len(fake.relation(jadore, "Families")) == 2

    third = prov.seed(refs, plan, update_existing=False)
    assert third["products"] == {"created": 0, "updated": 0, "skipped": 4}


def test_start_page_links_hubs_once():
    fake = FakeNotion()
    prov, refs = _provision(fake)
    prov.seed(refs, build_seed(SAMPLE_CATALOGS))

    page_id = prov.ensure_start_page(refs, prov.hub_pages(refs))
    again = prov.ensure_start_page(refs, prov.hub_pages(refs), known_id=page_id)
    by_title = prov.ensure_start_page(refs, prov.hub_pages(refs))
    assert page_id == again == by_title

    start_pages = [b for b in fake.children[fake.parent_page_id] if b["type"] == "child_page"]
    assert len(start_pages) == 1
    parent_links = [b for b in fake.children[fake.parent_page_id] if b["type"] == "link_to_page"]
    assert len(parent_links) == 1

    body = fake.children[page_id]
    linked_pages = {b["link_to_page"].get("page_id") for b in body if b["type"] == "link_to_page"}
    dior = fake.row(refs["brands"].data_source_id, "brand:dior")["id"]
    pricing = fake.row(refs["playbook"].data_source_id, "playbook:pricing")["id"]
    assert {dior, pricing} <= linked_pages
    linked_dbs = {b["link_to_page"].get("database_id") for b in body if b["type"] == "link_to_page"}
    assert {r.database_id for r in refs.values()} <= linked_dbs


def test_start_page_falls_back_to_text_links_for_databases():
    fake = FakeNotion(reject_database_links=True)
    prov, refs = _provision(fake)
    page_id = prov.ensure_start_page(refs, {"brands": [], "playbook": []})
    assert len([b for b in fake.children[fake.parent_page_id] if b["type"] == "child_page"]) == 1
    links = [
        r["text"]["link"]["url"]
        for b in fake.children[page_id] if b["type"] == "bulleted_list_item"
        for r in b["bulleted_list_item"]["rich_text"] if r["text"].get("link")
    ]
    assert f"https://www.notion.so/{refs['leads'].database_id.replace('-', '')}" in links


def test_env_values_cover_every_data_source():
    fake = FakeNotion()
    _, refs = _provision(fake)
    values = SetupResult(refs, start_page_id="start").env_values("ntn_x", fake.parent_page_id)
    assert set(DATA_SOURCE_ENV.values()) <= set(values)
    assert values["NOTION_START_PAGE_ID"] == "start"


# --- the script ---------------------------------------------------------------


def test_dry_run_calls_nothing_and_writes_nothing(tmp_path, monkeypatch, capsys):
    def refuse(*args, **kwargs):
        raise AssertionError("dry run made an HTTP request")

    monkeypatch.setattr(httpx.Client, "request", refuse)
    monkeypatch.setattr(httpx.Client, "send", refuse)
    env = tmp_path / ".env"
    monkeypatch.setattr(
        sys, "argv",
        ["setup_notion.py", "--dry-run", "--token", "ntn_secret_value", "--env-file", str(env),
         "--parent", "https://www.notion.so/ZUNO-1f2e3d4c5b6a47988a7b6c5d4e3f2a1b"],
    )
    spec = importlib.util.spec_from_file_location("setup_notion_script", REPO_ROOT / "scripts" / "setup_notion.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.main() == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "Products" in out and "1f2e3d4c-5b6a-4798-8a7b-6c5d4e3f2a1b" in out
    assert "ntn_secret_value" not in out
    assert not env.exists()
