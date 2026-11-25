"""The HTTP surface of the two-mode work: call start with a mode, the console's
mode toggle, the events poll, the catalog, product images and the knowledge
graph."""
import pytest
from fastapi.testclient import TestClient

from app.knowledge import graph
from app.main import app
from app.routes import catalog as catalog_routes
from app.sessions.models import SessionState
from app.sessions.store import session_store

from tests.perfume_support import perfume_catalog  # noqa: F401

client = TestClient(app)


class FakeAgora:
    def __init__(self):
        self.payloads = []

    def join(self, payload):
        self.payloads.append(payload)
        return {"agent_id": "agent-x"}

    def leave(self, agent_id):
        pass


@pytest.fixture
def agora(monkeypatch):
    fake = FakeAgora()
    monkeypatch.setattr("app.sessions.controller.default_agora_client", lambda: fake)
    return fake


def test_call_start_without_a_body_still_works_and_defaults_to_apple(agora):
    body = client.post("/api/call/start").json()
    assert body["mode"] == "apple"
    assert session_store.get(body["session_id"]).mode == "apple"
    assert "Apple" in agora.payloads[0]["properties"]["llm"]["greeting_message"]


def test_call_start_in_perfume_mode_greets_as_the_boutique(agora):
    body = client.post("/api/call/start", json={"mode": "perfume"}).json()
    assert body["mode"] == "perfume"
    assert session_store.get(body["session_id"]).mode == "perfume"
    greeting = agora.payloads[0]["properties"]["llm"]["greeting_message"]
    assert "beauty boutique" in greeting and "Dior" in greeting and "Apple" not in greeting


def test_call_start_rejects_an_unknown_mode(agora):
    assert client.post("/api/call/start", json={"mode": "chanel"}).status_code == 422


def test_events_carry_mode_and_spotlight():
    session = session_store.get_or_create("sess-events")
    session.spotlight = {"id": "apple-ipad", "name": "iPad"}
    body = client.get("/api/session/sess-events/events").json()
    assert body["mode"] == "apple"
    assert body["spotlight"] == {"id": "apple-ipad", "name": "iPad"}

    missing = client.get("/api/session/nope/events").json()
    assert missing["mode"] is None and missing["spotlight"] is None


def test_console_mode_toggle():
    # Without Agora credentials the default publisher is the in-memory
    # logger (rtm/publisher.py), so that is where the event lands here.
    from app.rtm.publisher import default_publisher

    before = len(default_publisher.events)
    session_store.save(SessionState(session_id="sess-toggle"))
    response = client.post("/api/session/sess-toggle/mode", json={"mode": "perfume"})
    assert response.status_code == 200
    assert response.json() == {"mode": "perfume"}
    assert session_store.get("sess-toggle").mode == "perfume"
    changed = [e for e in default_publisher.events[before:] if e.type == "mode_changed"]
    assert changed[0].payload == {"mode": "perfume", "previous": "apple", "by": "console"}
    assert client.get("/api/session/sess-toggle/events").json()["mode"] == "perfume"

    # Idempotent: the same mode again answers the mode, publishes nothing new.
    assert client.post("/api/session/sess-toggle/mode", json={"mode": "perfume"}).json() == {"mode": "perfume"}
    changed = [e for e in default_publisher.events[before:] if e.type == "mode_changed"]
    assert len(changed) == 1


def test_console_mode_toggle_errors():
    assert client.post("/api/session/missing/mode", json={"mode": "perfume"}).status_code == 404
    session_store.save(SessionState(session_id="sess-bad"))
    assert client.post("/api/session/sess-bad/mode", json={"mode": "chanel"}).status_code == 422


def test_catalog_listing_filters_and_search(perfume_catalog):
    body = client.get("/api/catalog", params={"mode": "perfume"}).json()
    assert body["mode"] == "perfume"
    assert len(body["products"]) == 6

    fragrance = client.get("/api/catalog", params={"mode": "perfume", "category": "fragrance"}).json()
    assert {p["category"] for p in fragrance["products"]} == {"fragrance"}

    rose = client.get("/api/catalog", params={"mode": "perfume", "q": "rose"}).json()["products"]
    assert rose and all("rose" in str(p).lower() for p in rose)

    apple = client.get("/api/catalog", params={"mode": "apple", "category": "ipad"}).json()
    assert apple["products"] and all(p["brand"] == "Apple" for p in apple["products"])

    assert client.get("/api/catalog", params={"mode": "chanel"}).status_code == 422


def test_catalog_product_lookup(perfume_catalog):
    body = client.get("/api/catalog/dior-sauvage-eau-de-parfum").json()
    assert body["name"] == "Sauvage Eau de Parfum"
    assert client.get("/api/catalog/apple-macbook-air-m5").json()["price_usd_from"] == 999
    assert client.get("/api/catalog/no-such-thing").status_code == 404


def test_product_image_is_fetched_once_then_cached(perfume_catalog, tmp_path, monkeypatch):
    monkeypatch.setattr(catalog_routes, "IMAGE_CACHE_DIR", tmp_path / "images")
    calls = []

    def fake_fetch(url, referer=None):
        calls.append((url, referer))
        return b"\xff\xd8jpegbytes", "image/jpeg"

    monkeypatch.setattr(catalog_routes, "fetch_image", fake_fetch)

    first = client.get("/api/catalog/dior-sauvage-eau-de-parfum/image")
    second = client.get("/api/catalog/dior-sauvage-eau-de-parfum/image")

    assert first.status_code == second.status_code == 200
    assert first.content == second.content == b"\xff\xd8jpegbytes"
    assert first.headers["content-type"] == "image/jpeg"
    assert second.headers["cache-control"] == "public, max-age=86400"
    assert len(calls) == 1
    assert calls[0][1] == "https://www.dior.com/en_hk/beauty/sauvage-edp"
    assert (tmp_path / "images" / "dior-sauvage-eau-de-parfum.jpg").exists()


def test_product_image_404s_without_an_image(perfume_catalog, monkeypatch, tmp_path):
    # An empty cache: a seeded local cache must not mask a missing image_url.
    monkeypatch.setattr(catalog_routes, "IMAGE_CACHE_DIR", tmp_path / "images")
    assert client.get("/api/catalog/dior-sauvage-elixir/image").status_code == 404
    assert client.get("/api/catalog/apple-ipad/image").status_code == 404
    assert client.get("/api/catalog/unknown/image").status_code == 404


def test_product_image_fetch_failure_is_a_502(perfume_catalog, tmp_path, monkeypatch):
    monkeypatch.setattr(catalog_routes, "IMAGE_CACHE_DIR", tmp_path / "images")

    def boom(url, referer=None):
        raise ValueError("not a raster image: image/svg+xml")

    monkeypatch.setattr(catalog_routes, "fetch_image", boom)
    assert client.get("/api/catalog/dior-sauvage-eau-de-parfum/image").status_code == 502


def test_browser_like_user_agent_is_sent(monkeypatch):
    seen = {}

    class Resp:
        headers = {"content-type": "image/webp"}
        content = b"webp"

        def raise_for_status(self):
            pass

    def fake_get(url, headers, timeout, follow_redirects):
        seen.update(headers)
        return Resp()

    monkeypatch.setattr(catalog_routes.httpx, "get", fake_get)
    assert catalog_routes.fetch_image("https://x.test/a.webp") == (b"webp", "image/webp")
    assert seen["User-Agent"].startswith("ZUNO-demo/")


def test_knowledge_graph_endpoint(tmp_path):
    body = client.get("/api/knowledge-graph", params={"mode": "apple"}).json()
    assert body["mode"] == "apple"
    assert body["nodes"] and body["links"]
    assert body["stats"]["nodes"] == len(body["nodes"])
    assert body["stats"]["extracted"] + body["stats"]["inferred"] <= body["stats"]["links"]
    assert body["stats"]["communities"] > 0

    graph.set_path("perfume", tmp_path / "missing.graph.json")
    try:
        assert client.get("/api/knowledge-graph", params={"mode": "perfume"}).status_code == 404
    finally:
        graph.reset()
    assert client.get("/api/knowledge-graph", params={"mode": "chanel"}).status_code == 422
