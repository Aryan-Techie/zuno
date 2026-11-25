"""Perfume mode end to end, short of a live call: per-mode knowledge base,
catalog stock, the no-discount rule enforced in code, the persona, the voice,
CRM tagging and the integration events."""
import json

import pytest

from app.agora.join_payload import build_join_payload
from app.config import Settings
from app.crm import service as crm_service
from app.crm.espo_store import _from_espo, _to_espo
from app.crm.models import Lead
from app.deal import boutique
from app.handoff import service as handoff_service
from app.inventory.store import EspoProductStore
from app.language.profiles import ENGLISH, HINDI, HINGLISH
from app.orchestrator import bridge_lines
from app.rag import perfume_docs, retriever
from app.sessions.models import SessionState
from app.tools import definitions, executor
from app.tools.prompts import PERFUME_SYSTEM_PROMPT, build_system_prompt
from app.voice import director

from tests.perfume_support import FIXTURE, bus_events, perfume_catalog  # noqa: F401


@pytest.fixture
def perfume_session(perfume_catalog):
    return SessionState(session_id="sess-perfume", mode="perfume")


# --- knowledge base -----------------------------------------------------------


def test_each_mode_searches_its_own_knowledge_base(perfume_catalog):
    perfume = retriever.search("do you do engraving", mode="perfume")
    assert perfume[0].source == "boutique_faq.md"
    assert "engraving" in perfume[0].text.lower()
    assert all(r.source != "faq.md" for r in retriever.search("trade-in", mode="perfume"))
    # Apple's index has never heard of gift wrap or Sauvage.
    assert retriever.search("sauvage engraving gift wrap", mode="apple") == []


def test_perfume_search_tool_uses_the_session_mode(perfume_session):
    result = executor.dispatch("search_pricing_rag", {"query": "rose floral eau de parfum"}, perfume_session)
    sources = {c["source"] for c in result["chunks"]}
    assert sources <= {"fragrance.md", "makeup.md", "skincare.md", "boutique_faq.md"}
    assert any("Miss Dior" in c["text"] or "J'adore" in c["text"] for c in result["chunks"])


def test_admin_reindex_still_rebuilds_apple(perfume_catalog):
    retriever.search("anything", mode="apple")
    retriever.search("anything", mode="perfume")
    retriever.reset_index()
    assert retriever._indexes == {}


def test_rendered_docs_group_fragrance_by_family_and_keep_prices():
    products = json.loads(FIXTURE.read_text())
    docs = perfume_docs.render(products)
    assert set(docs) == {"fragrance.md", "makeup.md", "skincare.md"}
    fragrance = docs["fragrance.md"]
    assert "# Floral fragrances" in fragrance and "# Fresh Spicy fragrances" in fragrance
    assert "100 ml HK$1,250" in fragrance
    assert "Top notes: Calabrian bergamot." in fragrance
    assert "## Rouge Dior Lipstick (Dior)" in docs["makeup.md"]
    assert "Key ingredients: longoza extract." in docs["skincare.md"]


def test_the_boutique_faq_is_marked_as_demo_policy():
    from app.rag.ingest import DOCS_PERFUME_DIR

    faq = (DOCS_PERFUME_DIR / "boutique_faq.md").read_text()
    assert "DEMO POLICIES" in faq and "not affiliated with Dior" in faq
    for topic in ("samples", "engraving", "gift wrap", "Delivery across Hong Kong", "Returns"):
        assert topic.lower() in faq.lower()


# --- stock -------------------------------------------------------------------


def test_perfume_stock_comes_from_the_catalog(perfume_session):
    result = executor.dispatch("check_inventory", {"product": "Sauvage", "quantity": 2}, perfume_session)
    assert result["found"] and result["product"] == "Sauvage Eau de Parfum"
    assert result["units_in_stock"] == 12 and result["availability"] == "in_stock"
    assert result["can_fulfil_now"] is True
    assert result["currency"] == "HKD"


def test_perfume_out_of_stock_names_real_alternatives(perfume_session):
    result = executor.dispatch("check_inventory", {"product": "Sauvage Elixir"}, perfume_session)
    assert result["availability"] == "out_of_stock"
    names = [p["product"] for p in result["in_stock_instead"]]
    assert names and "Sauvage Elixir" not in names
    catalog_names = {p["name"] for p in json.loads(FIXTURE.read_text())}
    assert set(names) <= catalog_names


def test_perfume_low_stock_and_misses(perfume_session):
    low = executor.dispatch("check_inventory", {"product": "Miss Dior"}, perfume_session)
    assert low["availability"] == "low_stock" and low["units_in_stock"] == 3
    miss = executor.dispatch("check_inventory", {"product": "Chanel Coco Mademoiselle"}, perfume_session)
    assert miss["found"] is False and miss["we_stock"]


def test_apple_mode_stock_is_unchanged():
    result = executor.dispatch("check_inventory", {"product": "iPad 10th gen"}, SessionState(session_id="s"))
    assert result["sku"] == "IPAD-10" and result["units_in_stock"] == 240


def test_espo_apple_stock_ignores_seeded_perfume_rows():
    class Client:
        def list(self, entity, max_size):
            return [
                {"sku": "IPAD-10", "name": "iPad 10th gen", "stockQty": 5},
                {"sku": "dior-sauvage-edp", "name": "Dior Sauvage", "stockQty": 9, "category": "fragrance"},
                {"sku": "ADMIN-X", "name": "Admin thing", "stockQty": 1, "category": "Vision"},
            ]

    assert [p.sku for p in EspoProductStore(Client()).all()] == ["IPAD-10", "ADMIN-X"]


# --- negotiation: luxury houses do not discount ---------------------------------


def test_an_individual_never_gets_a_percentage(perfume_session, monkeypatch):
    def no_desk(**_):
        raise AssertionError("the Apple deal desk must not be consulted in perfume mode")

    monkeypatch.setattr("app.deal.desk.consult", no_desk)
    perfume_session.spotlight = json.loads(FIXTURE.read_text())[0]
    result = executor.dispatch(
        "negotiate_deal",
        {"customer_ask": "can you do 20% off?", "requested_discount_pct": 20},
        perfume_session,
    )
    assert result["granted_discount_pct"] == 0
    assert result["currency"] == "HKD"
    assert any("sample" in c.lower() for c in result["offer_concessions"])
    assert any("gift wrap" in c.lower() for c in result["offer_concessions"])
    assert "HK$980" in result["price_summary"]
    assert "No discount" in result["guidance"]
    offer = perfume_session.negotiation.last_offer
    assert offer.clamped and "does not discount individual" in offer.clamp_reason


def test_even_a_model_claiming_corporate_gets_nothing_under_ten_pieces(perfume_session):
    result = executor.dispatch(
        "negotiate_deal",
        {
            "customer_ask": "5% for our office gifts?",
            "requested_discount_pct": 5,
            "corporate_gifting": True,
            "device_mix": [{"model": "Sauvage Eau de Parfum 100 ml", "quantity": 9}],
        },
        perfume_session,
    )
    assert result["granted_discount_pct"] == 0
    assert result["corporate_gifting_eligible"] is False


def test_corporate_gifting_of_ten_or_more_is_capped_at_five_percent(perfume_session):
    result = executor.dispatch(
        "negotiate_deal",
        {
            "customer_ask": "we need 20 for clients, can you do 15%?",
            "requested_discount_pct": 15,
            "corporate_gifting": True,
            "device_mix": [{"model": "Sauvage Eau de Parfum 100 ml", "quantity": 20}],
        },
        perfume_session,
    )
    assert result["granted_discount_pct"] == boutique.CORPORATE_MAX_DISCOUNT_PCT == 5
    assert result["authorised_by"] == "deal_desk"
    assert result["awaiting_human_approval"] is False
    assert result["ask_for_in_return"]
    # 20 x HK$1,250 = HK$25,000, less 5% = HK$23,750.
    assert "HK$25,000" in result["price_summary"] and "HK$23,750" in result["price_summary"]
    assert perfume_session.negotiation.last_offer.clamped


def test_a_company_on_record_counts_as_corporate(perfume_session):
    perfume_session.left_brain.company = "Harbour Bank"
    result = executor.dispatch(
        "negotiate_deal",
        {"customer_ask": "best price?", "device_mix": [{"model": "Miss Dior 50 ml", "quantity": 12}]},
        perfume_session,
    )
    assert result["granted_discount_pct"] == 5
    assert "HK$1,080" not in result["price_summary"] or "12 x" in result["price_summary"]


@pytest.mark.parametrize("asked", [0, 1, 4.99, 5, 30, 100])
def test_the_cap_holds_for_any_ask(asked):
    granted, *_ = boutique.authorise(requested_pct=asked, units=50, corporate=True, already_granted=0)
    assert 0 <= granted <= 5
    granted, *_ = boutique.authorise(requested_pct=asked, units=50, corporate=False, already_granted=0)
    assert granted == 0


def test_apple_negotiation_is_unchanged_by_perfume_mode():
    session = SessionState(session_id="sess-apple-deal")
    session.left_brain.user_count = 60
    result = executor.dispatch("negotiate_deal", {"customer_ask": "3% off?", "requested_discount_pct": 3}, session)
    assert result["granted_discount_pct"] == 3
    assert "$" in result["price_summary"] and "HK$" not in result["price_summary"]


# --- persona, tools, voice -----------------------------------------------------


def test_perfume_prompt_covers_the_consultation_and_the_rules():
    prompt = build_system_prompt("perfume")
    assert prompt.startswith(PERFUME_SYSTEM_PROMPT)
    for must in (
        "Who it is for",
        "occasion",
        "love and scents they cannot stand",
        "Budget, in Hong Kong dollars",
        "RECOMMEND ONLY FROM OUR CATALOG",
        "LUXURY HOUSES DO NOT DISCOUNT",
        "show_product",
        "crm_upsert_lead",
        "calendar_book_meeting",
        "not Dior itself",
    ):
        assert must in prompt, must
    assert "markdown" in prompt  # same spoken-style rules as the Apple persona


def test_perfume_mode_keeps_the_hindi_instruction(monkeypatch):
    monkeypatch.setattr("app.tools.prompts.get_settings", lambda: Settings(agent_language="hinglish"))
    prompt = build_system_prompt("perfume")
    assert HINGLISH.prompt_instruction in prompt
    assert "J'adore" in prompt.split(HINGLISH.prompt_instruction)[1]


def test_perfume_tools_are_described_for_the_boutique():
    perfume = {t["name"]: t for t in definitions.tools_for("perfume")}
    apple = {t["name"]: t for t in definitions.tools_for("apple")}
    assert "show_product" in perfume and "show_product" in apple
    assert "deployment engineer" in apple["ask_solutions_engineer"]["description"]
    assert "fragrance and skincare specialist" in perfume["ask_solutions_engineer"]["description"]
    assert "corporate_gifting" not in apple["negotiate_deal"]["input_schema"]["properties"]
    # The Apple list is not mutated by building the perfume one.
    assert apple["search_pricing_rag"]["description"].startswith("Search Zuno's product")


def test_perfume_greeting_in_every_language():
    for profile in (ENGLISH, HINDI, HINGLISH):
        assert "Dior" in profile.mode_greetings["perfume"]
        assert "Apple" not in profile.mode_greetings["perfume"]


def _payload(**settings):
    return build_join_payload(
        session_id="abcdef1234567890", channel_name="c", agent_rtc_uid=1, browser_rtc_uid=2,
        agent_token="t", llm_url="u", settings=Settings(**settings), mode="perfume",
    )


def test_perfume_call_starts_with_its_own_voice_on_minimax():
    tts = _payload(tts_vendor="minimax")["properties"]["tts"]["params"]
    assert tts["voice_setting"]["voice_id"] == "English_Graceful_Lady"
    # Sarvam keeps the verified speaker unless one is configured.
    assert _payload()["properties"]["tts"]["params"]["speaker"] == "priya"
    assert _payload(perfume_sarvam_speaker="kavya")["properties"]["tts"]["params"]["speaker"] == "kavya"


def test_director_resolves_the_perfume_voice_only_for_english_zuno():
    assert director.resolve_voice(ENGLISH, mode="perfume") == "English_Graceful_Lady"
    assert director.resolve_voice(ENGLISH, mode="apple") == ENGLISH.voice_id
    assert director.resolve_voice(HINGLISH, mode="perfume", language="hi") == "hindi_female_1_v2"
    assert director.resolve_voice(HINDI, mode="perfume") == HINDI.voice_id
    assert director.resolve_voice(ENGLISH, role="solutions", mode="perfume") == ENGLISH.agent_voices["solutions"]
    # No desk answers a boutique price question, so no desk voice either.
    assert director.agent_for_tools(["negotiate_deal"], "perfume") == "zuno"
    assert director.agent_for_tools(["negotiate_deal"], "apple") == "deal_desk"


def test_perfume_bridge_lines_never_mention_the_apple_back_office():
    for tool in ("search_pricing_rag", "ask_solutions_engineer", "negotiate_deal"):
        for _ in range(10):
            line = bridge_lines.line_for(tool, language="en", mode="perfume")
            assert "deployment" not in line and "deal desk" not in line and "pricing" not in line


# --- CRM and integration events -----------------------------------------------


def test_leads_are_tagged_with_the_mode(perfume_session, bus_events):
    executor.dispatch("crm_upsert_lead", {"name": "Mei"}, perfume_session)
    assert crm_service.get_lead("sess-perfume").mode == "perfume"
    [emitted] = bus_events.of("lead_upserted")
    assert emitted["mode"] == "perfume" and emitted["lead"]["name"] == "Mei"


def test_espo_store_maps_the_mode_field():
    payload = _to_espo(Lead(session_id="s", name="Mei", mode="perfume"))
    assert payload["cZunoMode"] == "perfume"
    assert _from_espo({"id": "1", "lastName": "Mei", "cZunoMode": "perfume"}).mode == "perfume"
    assert _from_espo({"id": "1", "lastName": "Mei", "cZunoMode": ""}).mode is None
    assert "cZunoMode" not in _to_espo(Lead(session_id="s"))


def test_objection_and_booking_events_carry_session_and_mode(perfume_session, bus_events):
    executor.dispatch("log_objection", {"topic": "pricing", "raised_text": "too dear"}, perfume_session)
    slots = executor.dispatch("calendar_check_availability", {}, perfume_session)["slots"]
    executor.dispatch("calendar_book_meeting", {"slot_id": slots[0]["id"]}, perfume_session)

    [objection] = bus_events.of("objection_logged")
    assert objection["mode"] == "perfume" and objection["objection"]["topic"] == "pricing"
    [booking] = bus_events.of("meeting_booked")
    assert booking["session_id"] == "sess-perfume" and booking["booking"]["booking_id"]
    assert crm_service.get_lead("sess-perfume").mode == "perfume"


def test_call_ended_carries_the_products_shown(perfume_session, bus_events, monkeypatch):
    perfume_session.products_mentioned = ["dior-sauvage-eau-de-parfum"]
    perfume_session.outcome = "follow_up"
    handoff_service.on_call_end(perfume_session)
    [ended] = bus_events.of("call_ended")
    assert ended["session_id"] == "sess-perfume" and ended["mode"] == "perfume"
    assert ended["products"] == ["dior-sauvage-eau-de-parfum"]
    assert ended["outcome"] == "follow_up"
    assert "summary" in ended
