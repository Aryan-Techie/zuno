"""NotionClient: pacing, retries, and the upsert/relation helpers."""
import httpx
import pytest

from app.notion.client import NotionClient, NotionError, plain_text
from app.notion.config import DEFAULT_NOTION_VERSION
from app.notion.schema import ZUNO_ID, build_properties, database_properties, SPECS
from tests.test_notion_fakes import FakeNotion


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(round(seconds, 3))
        self.now += seconds


def _client(handler, clock: FakeClock, **kwargs) -> NotionClient:
    kwargs.setdefault("max_rps", 0)
    return NotionClient(
        "ntn_test", transport=httpx.MockTransport(handler), sleep=clock.sleep, clock=clock, **kwargs
    )


def test_sends_pinned_version_and_bearer_token():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"object": "page", "id": "p1"})

    _client(handler, FakeClock()).retrieve_page("p1")
    assert seen["notion-version"] == DEFAULT_NOTION_VERSION == "2026-03-11"
    assert seen["authorization"] == "Bearer ntn_test"


def test_paces_requests_to_max_rps():
    clock = FakeClock()
    client = _client(lambda r: httpx.Response(200, json={}), clock, max_rps=2)
    for _ in range(3):
        client.retrieve_page("p1")
    # First request goes at once; each later one waits for its 0.5s slot.
    assert clock.sleeps == [0.5, 0.5]


def test_retries_429_honouring_retry_after():
    clock = FakeClock()
    answers = [httpx.Response(429, headers={"Retry-After": "2"}, json={"code": "rate_limited"}),
               httpx.Response(200, json={"id": "p1"})]
    client = _client(lambda r: answers.pop(0), clock)
    assert client.retrieve_page("p1") == {"id": "p1"}
    assert clock.sleeps == [2.0]


def test_retries_5xx_with_backoff_then_raises():
    clock = FakeClock()
    attempts = []

    def handler(request):
        attempts.append(1)
        return httpx.Response(502, json={"code": "bad_gateway", "message": "down"})

    client = _client(handler, clock, max_retries=3)
    with pytest.raises(NotionError) as info:
        client.retrieve_page("p1")
    assert info.value.status == 502
    assert len(attempts) == 4
    assert len(clock.sleeps) == 3
    assert clock.sleeps[0] < clock.sleeps[1] < clock.sleeps[2]


def test_network_errors_are_retried():
    clock = FakeClock()
    attempts = []

    def handler(request):
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json={"id": "p1"})

    assert _client(handler, clock).retrieve_page("p1")["id"] == "p1"
    assert len(attempts) == 2


def test_validation_errors_raise_without_retry():
    clock = FakeClock()
    attempts = []

    def handler(request):
        attempts.append(1)
        return httpx.Response(400, json={"code": "validation_error", "message": "bad property"})

    with pytest.raises(NotionError) as info:
        _client(handler, clock).update_page("p1", {})
    assert info.value.code == "validation_error"
    assert len(attempts) == 1 and clock.sleeps == []


def _brands(fake: FakeNotion, client: NotionClient) -> str:
    db = client.create_database(fake.parent_page_id, "Brands", database_properties(SPECS["brands"], {}))
    return db["data_sources"][0]["id"]


def test_upsert_by_zuno_id_is_idempotent():
    fake = FakeNotion()
    client = fake.client()
    ds = _brands(fake, client)

    first = client.upsert_page(ds, "brand:dior", build_properties("brands", {"Name": "Dior"}), children=[])
    second = client.upsert_page(ds, "brand:dior", build_properties("brands", {"Name": "Dior Beauty"}))

    assert first.created and not second.created
    assert first.page_id == second.page_id
    rows = fake.rows(ds)
    assert len(rows) == 1
    assert fake.text(rows[0], "Name") == "Dior Beauty"
    assert fake.text(rows[0], ZUNO_ID) == "brand:dior"
    assert second.previous is not None and plain_text(second.previous["properties"]["Name"]) == "Dior"


def test_create_database_fills_data_sources_from_partial_response():
    fake = FakeNotion(partial_database_response=True)
    client = fake.client()
    db = client.create_database(fake.parent_page_id, "Brands", database_properties(SPECS["brands"], {}))
    assert db["data_sources"][0]["id"] in fake.data_sources


def test_add_relation_merges_and_skips_noop_writes():
    fake = FakeNotion()
    client = fake.client()
    brands = _brands(fake, client)
    a = client.create_page(brands, build_properties("brands", {"Name": "A"}))["id"]
    b = client.create_page(brands, build_properties("brands", {"Name": "B"}))["id"]
    products = client.create_database(
        fake.parent_page_id, "Products", {"Name": {"title": {}}, "Brand": {"relation": {
            "data_source_id": brands, "type": "dual_property", "dual_property": {}}}}
    )["data_sources"][0]["id"]
    page = client.create_page(products, {"Brand": {"relation": [{"id": a}]}})["id"]

    assert client.add_relation(page, "Brand", [b, a]) == [a, b]
    patches = fake.count("PATCH", f"/pages/{page}")
    assert client.add_relation(page, "Brand", [a]) == [a, b]
    assert fake.count("PATCH", f"/pages/{page}") == patches
