"""The live mirror: register() gating, handler safety, relation wiring."""
import logging

import pytest

from app.integrations import bus
from app.notion import sync
from app.notion.catalog import CatalogIndex, build_seed
from app.notion.config import DATA_SOURCE_ENV
from app.notion.provision import Provisioner
from app.notion.sync import NotionMirror
from tests.test_notion_fakes import SAMPLE_CATALOGS, FakeNotion

SID = "sess-1"
LEAD = {
    "id": "lead-1",
    "session_id": SID,
    "name": "Jane Doe",
    "company": "Acme",
    "title": "Head of IT",
    "email": "jane@acme.test",
    "user_count": 40,
    "pain_points": ["old laptops", "slow support"],
    "decision_stage": "evaluating",
    "status": "qualified",
}


@pytest.fixture
def bus_snapshot():
    saved = {event: list(handlers) for event, handlers in bus._subscribers.items()}
    bus.clear()
    yield
    bus.clear()
    for event, handlers in saved.items():
        bus._subscribers[event].extend(handlers)


@pytest.fixture
def clean_env(monkeypatch):
    for name in ["NOTION_TOKEN", "NOTION_PARENT_PAGE_ID", *DATA_SOURCE_ENV.values()]:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


class _Catalog(CatalogIndex):
    def __init__(self) -> None:
        super().__init__()
        self._by_id = {p["id"]: {**p, "_mode": m} for m, ps in SAMPLE_CATALOGS.items() for p in ps}

    def get(self, product_id):
        return self._by_id.get(product_id)


def _setup(seed_products=True, **fake_kwargs):
    fake = FakeNotion(**fake_kwargs)
    prov = Provisioner(fake.client(), fake.parent_page_id, log=lambda _l: None)
    refs = prov.ensure_databases()
    if seed_products:
        prov.seed(refs, build_seed(SAMPLE_CATALOGS))
    ds = {k: r.data_source_id for k, r in refs.items()}
    mirror = NotionMirror(fake.client(), ds, catalog=_Catalog())
    return fake, ds, mirror


# --- register() ------------------------------------------------------------


def test_register_is_a_noop_when_unconfigured(bus_snapshot, clean_env, caplog):
    with caplog.at_level(logging.INFO, logger="zuno.notion"):
        sync.register()
    assert not any(bus._subscribers.get(event) for event in bus.EVENTS)
    lines = [r for r in caplog.records if r.name == "zuno.notion"]
    assert len(lines) == 1 and lines[0].levelno == logging.INFO
    assert "NOTION_TOKEN" in lines[0].getMessage()


def test_register_is_a_noop_with_token_but_no_databases(bus_snapshot, clean_env, caplog):
    clean_env.setenv("NOTION_TOKEN", "ntn_test")
    with caplog.at_level(logging.INFO, logger="zuno.notion"):
        sync.register()
    assert not any(bus._subscribers.get(event) for event in bus.EVENTS)
    assert "NOTION_DS_BRANDS" in caplog.records[-1].getMessage()
    assert "ntn_test" not in caplog.text


def test_register_subscribes_every_event_when_configured(bus_snapshot, clean_env):
    clean_env.setenv("NOTION_TOKEN", "ntn_test")
    for name in DATA_SOURCE_ENV.values():
        clean_env.setenv(name, f"ds-{name.lower()}")
    sync.register()
    for event in bus.EVENTS:
        assert len(bus._subscribers[event]) == 1, event


# --- handler safety --------------------------------------------------------


class _Exploding:
    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("Notion is down")

        return boom


def test_handlers_swallow_errors(bus_snapshot, monkeypatch, caplog):
    mirror = NotionMirror(_Exploding(), {k: f"ds-{k}" for k in DATA_SOURCE_ENV}, catalog=_Catalog())
    for event, handler in mirror.handlers().items():
        bus.subscribe(event, handler)
    monkeypatch.setattr(bus, "run_inline", True)

    payloads = {
        "lead_upserted": {"lead": LEAD},
        "product_spotlighted": {"product": SAMPLE_CATALOGS["perfume"][0]},
        "objection_logged": {"objection": {"topic": "pricing", "raised_text": "too dear"}},
        "meeting_booked": {"booking": {"id": "b1"}},
        "mode_changed": {"previous": "apple"},
        "call_ended": {"outcome": "follow_up", "summary": None, "products": []},
    }
    with caplog.at_level(logging.WARNING):
        for event, payload in payloads.items():
            handler = mirror.handlers()[event]
            handler({"session_id": SID, "mode": "perfume", **payload})  # direct: must not raise
            bus.emit(event, {"session_id": SID, "mode": "perfume", **payload})
    assert "Notion mirror skipped lead_upserted" in caplog.text


def test_handlers_ignore_empty_payloads():
    fake, ds, mirror = _setup(seed_products=False)
    before = len(fake.calls)
    for handler in mirror.handlers().values():
        handler({})
        handler(None)
    # Nothing to attach to: no "call:unknown" rows, no requests at all.
    assert len(fake.calls) == before


# --- wiring ----------------------------------------------------------------


def test_a_call_wires_lead_call_products_objections_and_meeting():
    fake, ds, mirror = _setup()
    h = mirror.handlers()
    base = {"session_id": SID, "mode": "perfume"}
    sauvage = SAMPLE_CATALOGS["perfume"][0]

    h["product_spotlighted"]({**base, "product": sauvage})  # before the caller is known
    h["lead_upserted"]({**base, "lead": LEAD})
    h["objection_logged"]({**base, "objection": {"topic": "pricing", "raised_text": "Too expensive", "attempts": 1}})
    h["objection_logged"]({**base, "objection": {
        "topic": "pricing", "raised_text": "Too expensive", "resolved": True,
        "resolution_text": "Price per wear is under HK$2", "attempts": 2}})
    h["meeting_booked"]({**base, "booking": {
        "id": "b1", "lead_id": "lead-1", "session_id": SID,
        "start": "2026-11-26T15:00:00+00:00", "end": "2026-11-26T15:30:00+00:00", "rep_name": "Sam"}})
    h["mode_changed"]({**base, "mode": "apple", "previous": "perfume", "by": "voice"})
    h["call_ended"]({**base, "mode": "apple", "outcome": "meeting_booked", "products": ["apple-macbook-air-m5"],
                     "summary": {"lead_id": "lead-1", "headline": "Wants Sauvage gift sets",
                                 "recommended_action": "Send quote", "urgency": "this_week",
                                 "facts": ["40 seats"], "duration_seconds": 312}})

    lead = fake.row(ds["leads"], "lead:lead-1")
    call = fake.row(ds["calls"], f"call:{SID}")
    product = fake.row(ds["products"], "product:dior-sauvage-eau-de-parfum")
    macbook = fake.row(ds["products"], "product:apple-macbook-air-m5")
    playbook = fake.row(ds["playbook"], "playbook:pricing")
    objection = fake.rows(ds["objections"])
    meeting = fake.row(ds["meetings"], "meeting:b1")

    assert len(fake.rows(ds["leads"])) == 1 and len(fake.rows(ds["calls"])) == 1
    assert fake.text(lead, "Name") == "Jane Doe (Acme)"
    assert fake.option(lead, "Stage") == "Qualified"
    assert fake.relation(lead, "Products of interest") == [product["id"], macbook["id"]]

    assert fake.text(call, "Name").startswith("Call · Jane Doe (Acme) · ")
    assert fake.relation(call, "Lead") == [lead["id"]]
    assert fake.relation(call, "Products mentioned") == [product["id"], macbook["id"]]
    assert fake.option(call, "Outcome") == "meeting booked"
    assert fake.option(call, "Mode") == "apple"
    assert fake.text(call, "Headline") == "Wants Sauvage gift sets"

    assert len(objection) == 1  # logged twice, one row
    objection = objection[0]
    assert fake.option(objection, "Status") == "Resolved"
    assert fake.relation(objection, "Call") == [call["id"]]
    assert fake.relation(objection, "Lead") == [lead["id"]]
    # No product named on the objection: the one on screen is used.
    assert fake.relation(objection, "Products") == [product["id"]]
    assert fake.relation(objection, "Playbook") == [playbook["id"]]

    answers = [b for b in fake.children[playbook["id"]] if b["type"] == "paragraph"
               and any(r["type"] == "mention" for r in b["paragraph"]["rich_text"])]
    assert len(answers) == 1
    mention = next(r for r in answers[0]["paragraph"]["rich_text"] if r["type"] == "mention")
    assert mention["mention"]["page"]["id"] == product["id"]

    assert fake.relation(meeting, "Lead") == [lead["id"]]
    assert fake.relation(meeting, "Call") == [call["id"]]
    assert fake.text(meeting, "Rep") == "Sam"

    body = fake.children[call["id"]]
    assert any(b["type"] == "heading_3" for b in body)  # the wrap-up
    assert any("Switched to apple mode" in "".join(r.get("text", {}).get("content", "")
               for r in b.get("paragraph", {}).get("rich_text", [])) for b in body)


def test_replayed_events_and_restarts_do_not_duplicate_rows():
    fake, ds, mirror = _setup()
    payload = {"session_id": SID, "mode": "apple", "lead": LEAD}
    mirror.handlers()["lead_upserted"](payload)
    mirror.handlers()["lead_upserted"]({**payload, "lead": {**LEAD, "email": None, "phone": "+852 1234"}})

    restarted = NotionMirror(fake.client(), ds, catalog=_Catalog())
    restarted.handlers()["lead_upserted"](payload)

    assert len(fake.rows(ds["leads"])) == 1
    assert len(fake.rows(ds["calls"])) == 1
    lead = fake.rows(ds["leads"])[0]
    # A later partial record does not blank what an earlier one wrote.
    assert lead["properties"]["Email"] == {"email": "jane@acme.test"}
    assert lead["properties"]["Phone"] == {"phone_number": "+852 1234"}


def test_repeat_spotlight_costs_no_requests():
    fake, ds, mirror = _setup()
    h = mirror.handlers()
    event = {"session_id": SID, "mode": "perfume", "product": SAMPLE_CATALOGS["perfume"][0]}
    h["product_spotlighted"](event)
    before = len(fake.calls)
    h["product_spotlighted"](event)
    assert len(fake.calls) == before


def test_unseeded_product_is_created_with_brand_family_and_notes():
    fake, ds, mirror = _setup(seed_products=False)
    jadore = SAMPLE_CATALOGS["perfume"][1]
    mirror.handlers()["product_spotlighted"]({"session_id": SID, "mode": "perfume", "product": jadore})

    product = fake.row(ds["products"], "product:dior-jadore-eau-de-parfum")
    assert fake.relation(product, "Brand") == [fake.row(ds["brands"], "brand:dior")["id"]]
    assert len(fake.relation(product, "Families")) == 2
    assert fake.relation(product, "Heart notes") == [fake.row(ds["notes"], "note:damascus-rose")["id"]]
    call = fake.row(ds["calls"], f"call:{SID}")
    assert fake.relation(call, "Products mentioned") == [product["id"]]


def test_objection_before_lead_is_linked_once_lead_arrives():
    fake, ds, mirror = _setup()
    h = mirror.handlers()
    base = {"session_id": SID, "mode": "apple"}
    h["objection_logged"]({**base, "objection": {"topic": "trust", "raised_text": "Never heard of you"}})
    h["lead_upserted"]({**base, "lead": LEAD})
    objection = fake.rows(ds["objections"])[0]
    assert fake.relation(objection, "Lead") == [fake.row(ds["leads"], "lead:lead-1")["id"]]


def test_status_written_as_select_when_setup_fell_back():
    fake, ds, mirror = _setup(reject_status=True)
    mirror.handlers()["lead_upserted"]({"session_id": SID, "mode": "apple", "lead": LEAD})
    lead = fake.row(ds["leads"], "lead:lead-1")
    assert lead["properties"]["Stage"] == {"select": {"name": "Qualified"}}
