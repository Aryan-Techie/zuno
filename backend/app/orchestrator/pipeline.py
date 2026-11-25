"""The core per-turn loop invoked by routes/llm.py (the endpoint Agora calls).

Memory recall/write-back (mem0) is wired in via app.memory.session_memory's
safe_recall/safe_write_back — both no-op with zero network calls whenever
Voyage/Anthropic keys aren't configured (the default in tests/dev without a
.env), so this stays hermetic to test without any extra mocking.
"""
import json
import logging
import time
from typing import Callable, Iterator

from app.catalogs import spotlight
from app.config import get_settings
from app.escalation import triggers
from app.escalation.models import TranscriptTurn
from app.language.profiles import strip_speech_markup
from app.memory.session_memory import safe_recall, safe_write_back
from app.modes import switch as mode_switch
from app.orchestrator import bridge_lines
from app.orchestrator.llm_client import (
    ChatLLMClient,
    LLMTurn,
    StreamingChatLLMClient,
    default_llm_client,
)
from app.rtm.publisher import RtmPublisher, default_rtm_publisher
from app.sessions.models import SessionState
from app.tools import definitions, executor
from app.voice import director
from app.tools.prompts import ZUNO_SYSTEM_PROMPT, build_system_prompt, supports_speech_markup

logger = logging.getLogger("zuno")

# 4 was not enough for the booking flow: check_availability -> book ->
# confirm burned every hop and the turn fell through to the fallback string
# with the confirmation unsaid. Most turns use 1-2 hops, so a higher ceiling
# costs nothing on the common path and only spends time when genuinely needed.
MAX_TOOL_HOPS = 6

QUALIFICATION_TOOLS = {"crm_upsert_lead", "crm_qualify_lead"}

MemoryRecallFn = Callable[[str, str], list[str]]
MemoryWriteBackFn = Callable[[str, str, str], None]


def _render_call_state(session: SessionState) -> str:
    """Renders LeftBrain/RightBrain into a compact block for the system prompt.

    The tools write these every single turn, but until now nothing ever read
    them back - the model only ever saw raw transcript. Re-injecting them is
    what lets Zuno hold on to a detail given twenty turns ago and notice when
    the customer *changes* one (the 25 -> 50 device-count case in the demo
    scenario), without paying a network round-trip to a memory service.

    Returns "" when nothing has been captured yet, so an untouched session
    leaves the system prompt byte-identical to ZUNO_SYSTEM_PROMPT.
    """
    left, right = session.left_brain, session.right_brain
    sections: list[str] = []

    facts: list[str] = []
    if left.name:
        facts.append(f"Speaking with: {left.name}" + (f", {left.title}" if left.title else ""))
    if left.company:
        facts.append(f"Company: {left.company}")
    if left.industry:
        facts.append(f"Industry: {left.industry}")
    if left.email or left.phone:
        contact = " / ".join(c for c in (left.email, left.phone) if c)
        facts.append(f"Contact on file: {contact}")
    if left.user_count is not None:
        what = "Pieces wanted" if session.mode == "perfume" else "Devices/users needed"
        facts.append(f"{what}: {left.user_count}")
    if left.budget_range:
        facts.append(f"Budget: {left.budget_range}")
    if left.timeline:
        facts.append(f"Timeline: {left.timeline}")
    if left.pain_points:
        facts.append("Pain points: " + "; ".join(left.pain_points))
    if left.decision_stage:
        facts.append(f"Decision stage: {left.decision_stage}")

    if facts:
        sections.append(
            "What you have already established on this call - treat it as fact "
            "and do NOT ask for it again. If the customer changes any of it, "
            "call crm_upsert_lead so this record updates:\n"
            + "\n".join(f"- {f}" for f in facts)
        )

    signals: list[str] = []
    for objection in right.objections:
        state = "resolved" if objection.resolved else "STILL UNRESOLVED"
        repeat = f", raised {objection.attempts} times" if objection.attempts > 1 else ""
        signals.append(f'- {objection.topic} ({state}{repeat}): "{objection.raised_text}"')
    if right.competitor_mentions:
        signals.append("- Competitors they have brought up: " + ", ".join(right.competitor_mentions))
    if right.sentiment != "neutral":
        signals.append(f"- Current read on their tone: {right.sentiment}")

    if signals:
        sections.append(
            "Objections raised and how they are feeling - an unresolved objection "
            "raised more than once needs a genuinely different answer, not a "
            "reworded one:\n" + "\n".join(signals)
        )

    negotiation = _render_negotiation(session)
    if negotiation:
        sections.append(negotiation)

    return "\n\n".join(sections)


def _render_negotiation(session: SessionState) -> str:
    """What she has already put on the table, and what she may still say.

    Without this she re-opens every round from zero: the tool result from two
    turns ago has scrolled out of the useful part of the history, and a
    negotiator who forgets her own last offer either repeats it as if it were
    new or, worse, contradicts it. The authorised figure is restated every
    hop, from the record rather than from the transcript, so what she believes
    she offered and what the business actually authorised cannot drift apart.
    """
    negotiation = session.negotiation
    offer = negotiation.last_offer
    if offer is None:
        return ""

    if session.mode == "perfume":
        return _render_boutique_negotiation(negotiation, offer)

    lines = [
        f"- You have already offered {negotiation.granted_discount_pct:g}% off list "
        f"(round {negotiation.round_count}, authorised by {offer.authorised_by}). "
        "That number stands - never go below it, and never present it again as if it were new.",
        f"- The numbers you gave, verbatim: {offer.price_summary}",
    ]
    if offer.commitments:
        lines.append(
            "- You asked for this in return, so hold them to it: "
            + "; ".join(c.detail for c in offer.commitments)
        )
    if negotiation.human_approved_pct is not None:
        lines.append(
            f"- Your sales manager has now approved {negotiation.human_approved_pct:g}%. "
            "You may offer that in your very next reply - lead with it, they have been waiting on it."
        )
    elif negotiation.pending_human_approval:
        lines.append(
            "- A sales manager is being asked about a larger discount right now. Say it is with "
            "your manager and you will confirm before the call ends. Do NOT state it as agreed."
        )
    lines.append(
        "- If they push again, call negotiate_deal again rather than moving on your own. "
        "Each round the desk allows less than the last, and that is deliberate."
    )
    return "Where the negotiation stands:\n" + "\n".join(lines)


def _render_boutique_negotiation(negotiation, offer) -> str:
    """Perfume mode's version of the above: there is no ladder to restate,
    only what was said about price and what was offered instead."""
    extras = "; ".join(c.detail for c in offer.concessions if c.kind != "discount")
    lines = [f"- The price as you gave it, verbatim: {offer.price_summary}"]
    if negotiation.granted_discount_pct:
        lines.append(
            f"- Corporate gifting pricing of {negotiation.granted_discount_pct:g}% is authorised and "
            "stands. It is the most the boutique gives - never offer more."
        )
    else:
        lines.append(
            "- No discount was given, and none can be: boutique prices are fixed. Never imply "
            "otherwise later in the call."
        )
    if extras:
        lines.append(f"- Complimentary extras you offered: {extras}")
    lines.append("- If they push again, call negotiate_deal again rather than answering on your own.")
    return "Where the price conversation stands:\n" + "\n".join(lines)


def _render_spotlight(session: SessionState) -> str:
    product = session.spotlight
    if not product:
        return ""
    return (
        f"On the customer's screen right now: {product.get('name')} (catalog id {product.get('id')}). "
        "If they say \"this one\" or \"it\", they most likely mean this product."
    )


def _build_system_prompt(
    session: SessionState, memories: list[str], mode_change: dict | None = None
) -> str:
    blocks = [build_system_prompt(session.mode)]

    if mode_change:
        blocks.append(mode_switch.switch_note(mode_change))

    call_state = _render_call_state(session)
    if call_state:
        blocks.append(call_state)

    on_screen = _render_spotlight(session)
    if on_screen:
        blocks.append(on_screen)

    if memories:
        memory_block = "\n".join(f"- {m}" for m in memories)
        blocks.append(
            "Relevant details recalled from earlier in this relationship/call "
            "(may be from beyond the visible recent history - use if relevant, "
            f"don't repeat back verbatim):\n{memory_block}"
        )

    return "\n\n".join(blocks)


def _history_to_anthropic_messages(session: SessionState) -> list[dict]:
    return [{"role": t.role, "content": t.content} for t in session.transcript]


def _turn_to_assistant_content(turn: LLMTurn) -> list[dict]:
    content: list[dict] = []
    if turn.text:
        content.append({"type": "text", "text": turn.text})
    for call in turn.tool_calls:
        block = {"type": "tool_use", "id": call.id, "name": call.name, "input": call.input}
        if call.thought_signature is not None:
            block["thought_signature"] = call.thought_signature
        content.append(block)
    return content


def _execute_tool_calls(
    turn: LLMTurn,
    session: SessionState,
    publisher: RtmPublisher,
    messages: list[dict],
) -> bool:
    """Runs one hop's tool calls, appends the assistant + tool_result messages,
    publishes the matching RTM events, and reports whether escalation fired.

    Shared by run_turn and run_turn_stream so the streaming path can never
    drift from the blocking one.
    """
    escalate_called = False
    messages.append({"role": "assistant", "content": _turn_to_assistant_content(turn)})
    tool_result_blocks = []

    for call in turn.tool_calls:
        session.tool_calls.append(call.name)
        publisher.publish(session.session_id, "tool_call_started", {"tool_name": call.name, "args": call.input})
        result = executor.dispatch(call.name, call.input, session)
        publisher.publish(
            session.session_id,
            "tool_call_finished",
            {
                "tool_name": call.name,
                "result_summary": json.dumps(result, default=str)[:300],
                # Real value behind the "low-confidence answer" guardrail
                # (app/escalation/triggers.py) - was previously invisible on
                # the console, which hardcoded the guard meter to 0.
                "rag_score": session.last_rag_score,
            },
        )

        if call.name == "escalate_to_human":
            escalate_called = True
            publisher.publish(session.session_id, "escalation_triggered", {"trigger_source": "llm", **result})
        elif call.name in QUALIFICATION_TOOLS:
            publisher.publish(session.session_id, "qualification_updated", session.left_brain.model_dump(mode="json"))
        elif call.name == "log_objection":
            publisher.publish(session.session_id, "objection_logged", result)
        elif call.name == "show_product" and result.get("newly_shown") and session.spotlight:
            spotlight.publish(session, session.spotlight, publisher)
        elif call.name == "calendar_book_meeting" and "error" not in result:
            publisher.publish(session.session_id, "call_outcome_set", {"outcome": "meeting_booked", **result})
        elif call.name == "negotiate_deal" and "error" not in result:
            offer = session.negotiation.last_offer
            publisher.publish(
                session.session_id,
                "deal_offer_made",
                {
                    "round": offer.round if offer else session.negotiation.round_count,
                    "requested_pct": offer.requested_discount_pct if offer else None,
                    "granted_pct": result.get("granted_discount_pct"),
                    "authorised_by": result.get("authorised_by"),
                    # The audit line: what the desk wanted, and what stopped it.
                    # Nothing else in the UI can show that a limit was enforced
                    # rather than merely respected.
                    "clamped": offer.clamped if offer else False,
                    "clamp_reason": offer.clamp_reason if offer else None,
                    "asked_in_return": result.get("ask_for_in_return", []),
                    # The rest of what the desk actually produced - the priced
                    # quote, its own reasoning, and every non-discount lever -
                    # so the console can show the whole round, not a 7-field
                    # summary of it.
                    "price_summary": offer.price_summary if offer else "",
                    "rationale": offer.rationale if offer else "",
                    "quote": offer.quote.model_dump(mode="json") if offer else None,
                    "concessions": [c.model_dump(mode="json") for c in offer.concessions] if offer else [],
                    "commitments": [c.model_dump(mode="json") for c in offer.commitments] if offer else [],
                    "requires_human": offer.requires_human if offer else False,
                    "declined": offer.declined if offer else False,
                    # USD for Apple, HKD at the boutique - the quote's numbers
                    # mean nothing without it.
                    "currency": result.get("currency", "USD"),
                    "mode": session.mode,
                },
            )
            if result.get("awaiting_human_approval"):
                publisher.publish(
                    session.session_id,
                    "deal_approval_requested",
                    {
                        "escalation_id": session.negotiation.approval_escalation_id,
                        "requested_pct": offer.requested_discount_pct if offer else None,
                    },
                )

        tool_result_blocks.append(
            {"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(result, default=str)}
        )

    messages.append({"role": "user", "content": tool_result_blocks})
    return escalate_called


def _begin_turn(session: SessionState, latest_user_message: str, publisher: RtmPublisher) -> dict | None:
    """What happens on the caller's words before the model sees them.

    1. A spoken mode switch ("Dior mode", "Apple mode") takes effect now, so
       this very turn's prompt, tools and catalog are the new mode's and the
       reply can acknowledge it. Returns the switch for the prompt note. A
       switch made from the console since the last turn is picked up here
       too, once.
    2. A catalog product the caller named goes on screen (deduped).

    Both are regex and dict work on local data - no network on the turn path.
    """
    change = mode_switch.from_utterance(session, latest_user_message, publisher)
    pending, session.pending_mode_switch = session.pending_mode_switch, None
    try:
        spotlight.from_text(session, latest_user_message, publisher)
    except Exception:
        logger.warning("spotlight from caller text failed", exc_info=True)
    return change or pending


def _spotlight_reply(session: SessionState, text: str, publisher: RtmPublisher, showed: bool) -> None:
    """The screen follows what Zuno says, too: a product she named in her
    reply goes on screen without her spending a hop on show_product. Skipped
    when she already called show_product this turn - that was a deliberate
    choice and a passing mention must not override it."""
    if showed or not text:
        return
    try:
        spotlight.from_text(session, strip_speech_markup(text), publisher)
    except Exception:
        logger.warning("spotlight from reply text failed", exc_info=True)


def run_turn(
    session: SessionState,
    history: list[TranscriptTurn],
    *,
    llm_client: ChatLLMClient | None = None,
    publisher: RtmPublisher | None = None,
    memory_recall: MemoryRecallFn = safe_recall,
    memory_write_back: MemoryWriteBackFn = safe_write_back,
    max_hops: int = MAX_TOOL_HOPS,
) -> str:
    """`history` is the full user/assistant turn history for this call, as
    provided by the caller for this request (Agora, in production). This is
    treated as the source of truth and overwrites session.transcript wholesale
    rather than being appended to our own locally-tracked copy — that's what
    correctly handles a barge-in: if the customer interrupted Zuno mid-reply,
    Agora's next request reflects the truncated version of what was actually
    said, not what Zuno intended to say.
    """
    llm_client = llm_client or default_llm_client()
    publisher = publisher or default_rtm_publisher()

    session.transcript = list(history)
    messages = _history_to_anthropic_messages(session)

    latest_user_message = next(
        (t.content for t in reversed(session.transcript) if t.role == "user"), ""
    )
    mode_change = _begin_turn(session, latest_user_message, publisher)
    recalled_memories = memory_recall(session.session_id, latest_user_message)

    escalate_called = False
    final_text = ""
    turn: LLMTurn | None = None
    showed = False

    for _hop in range(max_hops):
        # Rebuilt each hop: a tool called in the previous hop may have just
        # changed LeftBrain/RightBrain, and this hop should see the new value.
        system_prompt = _build_system_prompt(session, recalled_memories, mode_change)
        turn = llm_client.create_turn(
            system=system_prompt, messages=messages, tools=definitions.tools_for(session.mode)
        )

        if not turn.wants_tool_use:
            if not turn.text:
                # See run_turn_stream: an empty conclusion is dead air on a
                # live call, so re-sample rather than return silence.
                logger.warning("empty conclusion on hop=%d, re-sampling", _hop)
                continue
            final_text = turn.text
            break

        showed |= any(c.name == "show_product" for c in turn.tool_calls)
        escalate_called |= _execute_tool_calls(turn, session, publisher, messages)
    else:
        final_text = (turn.text if turn else "") or (
            "Sorry, I got a bit tangled up there. Could you say that again?"
        )
        logger.warning("Hit MAX_TOOL_HOPS (%d) without a final text answer, session=%s", max_hops, session.session_id)

    # Deterministic guardrails temporarily disabled — the LLM's own judgment
    # (already instructed to treat escalation as a last resort) is the only
    # path to escalate for now, while premature-escalation behavior is being
    # tuned live. Re-enable by flipping ESCALATION_GUARDRAILS_ENABLED.
    if get_settings().escalation_guardrails_enabled:
        should_escalate, source = triggers.check_triggers(session.right_brain, session.last_rag_score)
        if should_escalate and not escalate_called and session.status != "escalated":
            result = executor.dispatch(
                "escalate_to_human",
                {"reason": f"auto-triggered ({source})"},
                session,
                trigger_source=source,
            )
            publisher.publish(session.session_id, "escalation_triggered", {"trigger_source": source, **result})
            final_text += (
                " I'm also going to loop in one of our specialists who'll have full context, "
                "just to make sure you're fully taken care of."
            )

    _spotlight_reply(session, final_text, publisher, showed)
    session.transcript.append(TranscriptTurn(role="assistant", content=final_text))
    logger.info("session=%s final_text=%r", session.session_id, final_text)
    memory_write_back(session.session_id, latest_user_message, final_text)
    return final_text


def run_turn_stream(
    session: SessionState,
    history: list[TranscriptTurn],
    *,
    llm_client: StreamingChatLLMClient | None = None,
    publisher: RtmPublisher | None = None,
    memory_recall: MemoryRecallFn = safe_recall,
    memory_write_back: MemoryWriteBackFn = safe_write_back,
    max_hops: int = MAX_TOOL_HOPS,
) -> Iterator[str]:
    """Streaming twin of run_turn: yields reply text as it is generated.

    Same tool loop, same session bookkeeping - the only difference is that
    text is handed out token-by-token instead of after the whole loop. That
    matters because Agora starts TTS on the first chunk it receives, so the
    customer hears the opening words while later tool hops are still running,
    instead of waiting ~10s in silence and tripping Agora's own
    `failure_message` timeout.
    """
    llm_client = llm_client or default_llm_client()
    publisher = publisher or default_rtm_publisher()

    session.transcript = list(history)
    messages = _history_to_anthropic_messages(session)

    latest_user_message = next(
        (t.content for t in reversed(session.transcript) if t.role == "user"), ""
    )
    # Before the voice follow below, so a spoken mode switch is already in
    # force when the voice for this turn is chosen.
    mode_change = _begin_turn(session, latest_user_message, publisher)
    recalled_memories = memory_recall(session.session_id, latest_user_message)
    director.follow(
        session, spoken_language=director.script_language(latest_user_message)
    )

    escalate_called = False
    spoken_parts: list[str] = []
    turn: LLMTurn | None = None
    # At most one bridge line per turn. Two in a row ("let me pull those up"
    # ... "let me pull those up") is worse than none, and a turn that chains
    # three hops would otherwise get one before each.
    bridged = False
    showed = False

    for _hop in range(max_hops):
        system_prompt = _build_system_prompt(session, recalled_memories, mode_change)

        turn = None
        hop_text: list[str] = []
        hop_started = time.monotonic()

        # Buffered rather than yielded live, because some models (Qwen on Groq
        # notably) write out a complete answer AND call a tool in the same hop,
        # then answer again once the tool returns. Streaming both made Zuno say
        # the whole thing twice on a live call. Text is only spoken from a hop
        # that is NOT calling a tool - i.e. the hop that actually concludes the
        # turn.
        for kind, value in llm_client.stream_turn(
            system=system_prompt, messages=messages, tools=definitions.tools_for(session.mode)
        ):
            if kind == "text":
                hop_text.append(value)
            else:
                turn = value

        logger.info(
            "session=%s hop=%d took %.2fs tools=%s",
            session.session_id,
            _hop,
            time.monotonic() - hop_started,
            [c.name for c in turn.tool_calls] if turn else [],
        )

        if turn is None or not turn.wants_tool_use:
            text = "".join(hop_text)
            if text:
                spoken_parts.append(text)
                # Before the yield: once the text is handed to Agora the
                # generator may be closed by a barge-in and never resume.
                _spotlight_reply(session, text, publisher, showed)
                yield text
                break
            # Concluded with no tool call AND nothing to say - observed live on
            # a real turn, and it reaches the customer as dead air. Re-sample
            # instead of breaking; if every remaining hop also comes back empty
            # the loop falls through to the spoken fallback below.
            logger.warning(
                "empty conclusion on hop=%d, re-sampling, session=%s", _hop, session.session_id
            )
            continue

        # Speak BEFORE dispatching, so the line covers the tool's own runtime
        # plus the follow-up hop that turns its result into an answer - live
        # that pair measured 4.6s + 3.4s of dead air. Only for tools the
        # customer is actually waiting on, and only once per turn.
        if not bridged:
            waited_on = bridge_lines.speakable_tool([c.name for c in turn.tool_calls])
            line = bridge_lines.line_for(waited_on, mode=session.mode) if waited_on else None
            if line and not supports_speech_markup(get_settings()):
                line = strip_speech_markup(line)
            if line:
                bridged = True
                spoken_parts.append(line)
                yield line

        showed |= any(c.name == "show_product" for c in turn.tool_calls)
        escalate_called |= _execute_tool_calls(turn, session, publisher, messages)

        role = director.agent_for_tools([c.name for c in turn.tool_calls], session.mode)
        if role != "zuno":
            director.follow(session, role=role)
    else:
        if not spoken_parts:
            fallback = "Let me pull that up for you - one moment."
            spoken_parts.append(fallback)
            yield fallback
        logger.warning(
            "Hit MAX_TOOL_HOPS (%d) without a final text answer, session=%s", max_hops, session.session_id
        )

    if get_settings().escalation_guardrails_enabled:
        should_escalate, source = triggers.check_triggers(session.right_brain, session.last_rag_score)
        if should_escalate and not escalate_called and session.status != "escalated":
            result = executor.dispatch(
                "escalate_to_human",
                {"reason": f"auto-triggered ({source})"},
                session,
                trigger_source=source,
            )
            publisher.publish(session.session_id, "escalation_triggered", {"trigger_source": source, **result})
            tail = (
                " I'm also going to loop in one of our specialists who'll have full context, "
                "just to make sure you're fully taken care of."
            )
            spoken_parts.append(tail)
            yield tail

    final_text = "".join(spoken_parts)
    session.transcript.append(TranscriptTurn(role="assistant", content=final_text))
    logger.info("session=%s streamed final_text=%r", session.session_id, final_text)
    memory_write_back(session.session_id, latest_user_message, final_text)
