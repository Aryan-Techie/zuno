"""Two businesses, one agent: detecting a spoken mode switch, applying it, and
making the very turn that heard it answer in the new persona."""
import pytest

from app.config import Settings
from app.crm import service as crm_service
from app.deal.models import NegotiationState, Offer, Quote
from app.escalation.models import TranscriptTurn
from app.modes import coerce_mode, detect_requested_mode
from app.modes.switch import switch_mode
from app.orchestrator import pipeline
from app.orchestrator.llm_client import LLMTurn
from app.rtm.publisher import LoggingPublisher
from app.sessions.models import SessionState
from app.tools.prompts import PERFUME_SYSTEM_PROMPT, ZUNO_SYSTEM_PROMPT

from tests.perfume_support import RecordingLLM, bus_events, perfume_catalog  # noqa: F401


# --- detection ---------------------------------------------------------------


@pytest.mark.parametrize(
    "said, expected",
    [
        ("Dior mode", "perfume"),
        ("can we switch to perfume mode please", "perfume"),
        ("Fragrance mode.", "perfume"),
        ("Dior-mode!", "perfume"),
        ("okay, apple mode", "apple"),
        ("Apple mode again", "apple"),
        ("डियोर मोड में चलो", "perfume"),
        # Both said: the sentence ends up where the last one is.
        ("switch from apple mode to dior mode", "perfume"),
        ("go from Dior mode back to Apple mode", "apple"),
    ],
)
def test_a_spoken_switch_is_recognised(said, expected):
    assert detect_requested_mode(said) == expected


@pytest.mark.parametrize(
    "said",
    [
        "what's my mode of payment",
        "I'd like a perfume for my wife",
        "we're an Apple shop, mostly MacBooks",
        "is this in dark mode",
        "the Apple model with the bigger screen",
        "I love that perfume. Mode of transport is a car though",
        "a fragrance moderately priced",
        "please don't switch to Dior mode",
        "not apple mode",
        "",
        None,
    ],
)
def test_ordinary_speech_never_switches(said):
    assert detect_requested_mode(said) is None


def test_a_bad_default_mode_setting_falls_back_to_apple():
    assert coerce_mode("PERFUME") == "perfume"
    assert coerce_mode("chanel") == "apple"
    assert coerce_mode(None) == "apple"


def test_new_sessions_start_in_the_default_mode(monkeypatch):
    assert SessionState(session_id="s").mode == "apple"
    monkeypatch.setattr("app.config.get_settings", lambda: Settings(default_mode="perfume"))
    assert SessionState(session_id="s2").mode == "perfume"


# --- applying a switch -------------------------------------------------------


def test_switch_publishes_resets_and_emits(bus_events):
    session = SessionState(session_id="sess-switch")
    session.spotlight = {"id": "apple-ipad", "name": "iPad"}
    session.negotiation.rounds.append(
        Offer(round=1, customer_ask="10% off?", quote=Quote(units=50), granted_discount_pct=8)
    )
    session.negotiation.granted_discount_pct = 8
    publisher = LoggingPublisher()

    assert switch_mode(session, "perfume", by="console", publisher=publisher, follow_voice=False)

    assert session.mode == "perfume"
    assert session.spotlight is None
    # An Apple discount must not follow the caller to the boutique counter.
    assert session.negotiation == NegotiationState()
    [event] = [e for e in publisher.events if e.type == "mode_changed"]
    assert event.payload == {"mode": "perfume", "previous": "apple", "by": "console"}
    [emitted] = bus_events.of("mode_changed")
    assert emitted == {"session_id": "sess-switch", "mode": "perfume", "previous": "apple", "by": "console"}
    # A console switch is handed to the next turn's prompt.
    assert session.pending_mode_switch == {"mode": "perfume", "previous": "apple", "by": "console"}


def test_switching_to_the_mode_already_in_force_is_a_no_op(bus_events):
    session = SessionState(session_id="sess-same")
    publisher = LoggingPublisher()
    assert not switch_mode(session, "apple", by="voice", publisher=publisher)
    assert publisher.events == []
    assert bus_events.events == []


def test_switch_retags_an_existing_lead_off_the_turn_path(bus_events):
    session = SessionState(session_id="sess-retag")
    lead = crm_service.upsert_lead("sess-retag", name="Mei", mode="apple")
    session.crm_lead_id = lead.id
    queued = []

    switch_mode(
        session, "perfume", by="voice", publisher=LoggingPublisher(), follow_voice=False,
        runner=lambda fn, *args: queued.append((fn, args)),
    )

    # Nothing written yet - the CRM write is queued, not done inline.
    assert crm_service.get_lead("sess-retag").mode == "apple"
    fn, args = queued[0]
    fn(*args)
    assert crm_service.get_lead("sess-retag").mode == "perfume"
    assert bus_events.of("lead_upserted")[0]["mode"] == "perfume"


# --- the turn that hears it ---------------------------------------------------


def _run(session, text, llm, publisher=None):
    return pipeline.run_turn(
        session,
        [TranscriptTurn(role="user", content=text)],
        llm_client=llm,
        publisher=publisher or LoggingPublisher(),
        memory_recall=lambda *_: [],
        memory_write_back=lambda *_: None,
    )


def test_saying_dior_mode_switches_before_the_model_runs(perfume_catalog, bus_events):
    session = SessionState(session_id="sess-voice-switch")
    publisher = LoggingPublisher()
    llm = RecordingLLM([LLMTurn(text="Of course - welcome to the boutique, I'm Zuno.")])

    _run(session, "Can we go to Dior mode?", llm, publisher)

    assert session.mode == "perfume"
    system = llm.systems[0]
    # This turn already runs as the boutique advisor, with the boutique's tools...
    assert system.startswith(PERFUME_SYSTEM_PROMPT)
    assert "MODE SWITCH, THIS TURN" in system
    assert "acknowledging the switch" in system
    negotiate = next(t for t in llm.tools[0] if t["name"] == "negotiate_deal")
    assert "corporate_gifting" in negotiate["input_schema"]["properties"]
    # ...and the console and the integrations hear it with by="voice".
    [event] = [e for e in publisher.events if e.type == "mode_changed"]
    assert event.payload["by"] == "voice"
    assert bus_events.of("mode_changed")[0]["by"] == "voice"
    # A voice switch is answered by this turn, so nothing is left pending.
    assert session.pending_mode_switch is None


def test_the_switch_note_lasts_one_turn_only(perfume_catalog):
    session = SessionState(session_id="sess-one-turn")
    _run(session, "fragrance mode", RecordingLLM([LLMTurn(text="Welcome.")]))
    llm = RecordingLLM([LLMTurn(text="Lovely.")])
    _run(session, "it's for my sister", llm)
    assert session.mode == "perfume"
    assert "MODE SWITCH" not in llm.systems[0]
    assert llm.systems[0].startswith(PERFUME_SYSTEM_PROMPT)


def test_apple_mode_switches_back():
    session = SessionState(session_id="sess-back", mode="perfume")
    llm = RecordingLLM([LLMTurn(text="Sure thing.")])
    _run(session, "okay, Apple mode", llm)
    assert session.mode == "apple"
    assert llm.systems[0].startswith(ZUNO_SYSTEM_PROMPT)


def test_my_mode_of_payment_does_not_switch():
    session = SessionState(session_id="sess-payment")
    publisher = LoggingPublisher()
    llm = RecordingLLM([LLMTurn(text="We take cards.")])
    _run(session, "what's my mode of payment going to be?", llm, publisher)
    assert session.mode == "apple"
    assert not [e for e in publisher.events if e.type == "mode_changed"]
    assert "MODE SWITCH" not in llm.systems[0]


def test_a_console_switch_is_bridged_on_the_next_turn(perfume_catalog):
    session = SessionState(session_id="sess-console")
    switch_mode(session, "perfume", by="console", publisher=LoggingPublisher(), follow_voice=False)
    llm = RecordingLLM([LLMTurn(text="Now, a fragrance...")])
    _run(session, "so what do you have?", llm)
    assert "your team has just moved this call" in llm.systems[0]
    assert session.pending_mode_switch is None


def test_the_streaming_path_switches_too(perfume_catalog):
    class StreamingLLM:
        def __init__(self):
            self.systems = []

        def stream_turn(self, *, system, messages, tools):
            self.systems.append(system)
            yield "text", "Welcome to the boutique."
            yield "turn", LLMTurn(text="Welcome to the boutique.")

    session = SessionState(session_id="sess-stream-switch")
    llm = StreamingLLM()
    out = "".join(
        pipeline.run_turn_stream(
            session,
            [TranscriptTurn(role="user", content="perfume mode")],
            llm_client=llm,
            publisher=LoggingPublisher(),
            memory_recall=lambda *_: [],
            memory_write_back=lambda *_: None,
        )
    )
    assert out == "Welcome to the boutique."
    assert session.mode == "perfume"
    assert "MODE SWITCH, THIS TURN" in llm.systems[0]
