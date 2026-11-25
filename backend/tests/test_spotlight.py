"""The product card on screen: alias matching, dedupe, the show_product tool,
and the deterministic spotlight from the caller's words."""
from app.catalogs import catalog, spotlight
from app.escalation.models import TranscriptTurn
from app.orchestrator import pipeline
from app.orchestrator.llm_client import LLMTurn, ToolCall
from app.rtm.publisher import LoggingPublisher
from app.sessions.models import SessionState
from app.tools import executor

from tests.perfume_support import RecordingLLM, bus_events, perfume_catalog  # noqa: F401


def _id(text, mode):
    product = catalog.match_alias(text, mode)
    return product["id"] if product else None


def test_longest_alias_wins(perfume_catalog):
    assert _id("is sauvage elixir stronger than sauvage", "perfume") == "dior-sauvage-elixir"
    assert _id("the ipad pro please", "apple") == "apple-ipad-pro-m5"
    assert _id("just an ipad", "apple") == "apple-ipad"


def test_aliases_match_on_word_boundaries_only(perfume_catalog):
    assert _id("iphone 17e", "apple") == "apple-iphone-17e"
    assert _id("sauvageness", "perfume") is None
    assert _id("two macbook airs", "apple") == "apple-macbook-air-m5"


def test_apostrophes_and_accents_do_not_stop_a_match(perfume_catalog):
    assert _id("I wear J’adore", "perfume") == "dior-jadore-eau-de-parfum"


def test_generic_single_word_aliases_are_ignored(perfume_catalog):
    # "capture" is listed as an alias in the fixture, and is ordinary English.
    assert _id("I want to capture that feeling", "perfume") is None
    assert _id("tell me about capture totale", "perfume") == "dior-capture-totale-serum"


def test_each_mode_matches_only_its_own_catalog(perfume_catalog):
    assert _id("sauvage", "apple") is None
    assert _id("macbook air", "perfume") is None


def test_spotlight_dedupes_for_twenty_seconds():
    session = SessionState(session_id="sess-dedupe")
    product = catalog.get("apple-ipad")
    assert spotlight.mark(session, product, now=1000.0)
    assert not spotlight.mark(session, product, now=1019.0)
    assert spotlight.mark(session, product, now=1020.5)
    assert session.products_mentioned == ["apple-ipad"]


def test_caller_naming_a_product_puts_it_on_screen(perfume_catalog, bus_events):
    session = SessionState(session_id="sess-said", mode="perfume")
    publisher = LoggingPublisher()
    pipeline.run_turn(
        session,
        [TranscriptTurn(role="user", content="How much is Miss Dior?")],
        llm_client=RecordingLLM([LLMTurn(text="Let me check.")]),
        publisher=publisher,
        memory_recall=lambda *_: [],
        memory_write_back=lambda *_: None,
    )
    shown = [e for e in publisher.events if e.type == "product_spotlight"]
    assert shown[0].payload["product"]["id"] == "dior-miss-dior-eau-de-parfum"
    assert session.spotlight["id"] == "dior-miss-dior-eau-de-parfum"
    [emitted] = bus_events.of("product_spotlighted")
    assert emitted["session_id"] == "sess-said" and emitted["mode"] == "perfume"


def test_show_product_tool_publishes_once(perfume_catalog, bus_events):
    session = SessionState(session_id="sess-tool", mode="perfume")
    publisher = LoggingPublisher()
    call = lambda i: LLMTurn(  # noqa: E731
        text="", stop_reason="tool_use",
        tool_calls=[ToolCall(id=f"t{i}", name="show_product", input={"product": "Sauvage Elixir"})],
    )
    pipeline.run_turn(
        session,
        [TranscriptTurn(role="user", content="something stronger please")],
        llm_client=RecordingLLM([call(1), call(2), LLMTurn(text="It's an elixir.")]),
        publisher=publisher,
        memory_recall=lambda *_: [],
        memory_write_back=lambda *_: None,
    )
    shown = [e for e in publisher.events if e.type == "product_spotlight"]
    assert len(shown) == 1
    assert shown[0].payload["product"]["id"] == "dior-sauvage-elixir"
    assert len(bus_events.of("product_spotlighted")) == 1


def test_show_product_returns_catalog_facts_and_refuses_unknowns(perfume_catalog):
    session = SessionState(session_id="sess-facts", mode="perfume")
    result = executor.dispatch("show_product", {"product": "Sauvage Eau de Parfum"}, session)
    assert result["shown"] and result["newly_shown"]
    assert {"label": "100 ml", "price": "HK$1,250"} in result["product"]["sizes"]
    assert result["product"]["family"] == "Fresh Spicy"

    missing = executor.dispatch("show_product", {"product": "Chanel No 5"}, session)
    assert missing["shown"] is False and missing["error"] == "not_in_catalog"


def test_show_product_works_in_apple_mode():
    session = SessionState(session_id="sess-apple-show")
    result = executor.dispatch("show_product", {"product": "MacBook Air (M5)"}, session)
    assert result["product"]["sizes"] == [{"label": "13-inch", "price": "$999"}]


def test_a_product_named_in_the_reply_goes_on_screen():
    session = SessionState(session_id="sess-reply")
    publisher = LoggingPublisher()
    pipeline.run_turn(
        session,
        [TranscriptTurn(role="user", content="something light for travel")],
        llm_client=RecordingLLM([LLMTurn(text="The MacBook Air is the one I'd pick.")]),
        publisher=publisher,
        memory_recall=lambda *_: [],
        memory_write_back=lambda *_: None,
    )
    assert session.spotlight["id"] == "apple-macbook-air-m5"
