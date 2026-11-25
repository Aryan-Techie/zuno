"""Changing mode mid-call, by voice or from the console.

Both paths end in `switch_mode`, so a switch looks the same to the console and
to the integrations whichever way it was asked for - only `by` differs.

What a switch resets, and why
-----------------------------
* The spotlight: the card on screen belongs to the other catalog.
* The negotiation: rounds priced in dollars against Apple's ladder mean
  nothing against a boutique price list, and rendering "you already offered
  8% off" into a perfume consultation would have her honour a discount the
  boutique never gave.

What it keeps: everything about the caller (name, contact details, the lead
record). They are the same person whichever counter they are standing at.

Latency: nothing here waits on the network. The CRM re-tag and the voice
change both run in the background; the event publish appends to the session.
"""
from __future__ import annotations

import logging

from app import bus_events
from app.background import run_in_background
from app.deal.models import NegotiationState
from app.modes import MODE_LABELS, Mode, detect_requested_mode

logger = logging.getLogger("zuno.modes")


def _retag_lead(session) -> None:
    """Background: the lead's mode field follows the call. A CRM write, so it
    must never run on the turn path."""
    from app.crm import service as crm_service

    lead = crm_service.upsert_lead(session.session_id, mode=session.mode)
    bus_events.emit("lead_upserted", session, lead=lead.model_dump(mode="json"))


def switch_mode(
    session,
    mode: Mode,
    *,
    by: str,
    publisher=None,
    follow_voice: bool = True,
    runner=run_in_background,
) -> bool:
    """Put the session in `mode`. Returns False when it already was."""
    if mode == session.mode:
        return False

    if publisher is None:
        from app.rtm.publisher import default_rtm_publisher

        publisher = default_rtm_publisher()

    previous = session.mode
    session.mode = mode
    session.spotlight = None
    session.negotiation = NegotiationState()
    # The console's switch is picked up by the next turn's prompt; a voice
    # switch is answered by the very turn that heard it (see pipeline.py).
    session.pending_mode_switch = (
        {"mode": mode, "previous": previous, "by": by} if by != "voice" else None
    )
    logger.info("session=%s mode %s -> %s (by %s)", session.session_id, previous, mode, by)

    publisher.publish(
        session.session_id, "mode_changed", {"mode": mode, "previous": previous, "by": by}
    )
    bus_events.emit("mode_changed", session, previous=previous, by=by)

    if session.crm_lead_id:
        runner(_retag_lead, session)

    if follow_voice:
        try:
            from app.voice import director

            director.follow(session)
        except Exception:
            logger.warning("voice follow after mode switch failed", exc_info=True)
    return True


def from_utterance(session, text: str | None, publisher) -> dict | None:
    """Switch if the caller's words ask for it. Returns the switch (mode,
    previous, by) when one happened, so the turn can acknowledge it."""
    requested = detect_requested_mode(text)
    if requested is None:
        return None
    previous = session.mode
    # The pipeline follows the voice itself straight after this, with the
    # caller's language in hand - doing it here too would buy two updates.
    if not switch_mode(session, requested, by="voice", publisher=publisher, follow_voice=False):
        return None
    return {"mode": requested, "previous": previous, "by": "voice"}


def switch_note(switch: dict) -> str:
    """The one-turn instruction that makes the reply acknowledge a switch in
    the new persona, instead of carrying on as if the transcript above (still
    in the old persona) were the current job."""
    mode, previous = switch["mode"], switch["previous"]
    if switch.get("by") == "voice":
        opening = (
            f"MODE SWITCH, THIS TURN: the caller has just asked to switch from "
            f"{MODE_LABELS[previous]} to {MODE_LABELS[mode]}, and that is done."
        )
        ask = (
            "Open this reply by acknowledging the switch in ONE short, warm line, in your new "
            "role - for example "
            + (
                '"Of course - welcome to the boutique, I\'m Zuno, your beauty advisor."'
                if mode == "perfume"
                else '"Sure thing - back to Apple, I\'m Zuno from Apple sales."'
            )
            + " Then answer anything else they said in the same breath, and ask your first "
            "question for this role."
        )
    else:
        opening = (
            f"MODE SWITCH: your team has just moved this call from {MODE_LABELS[previous]} to "
            f"{MODE_LABELS[mode]}."
        )
        ask = (
            "Carry on in the new role from this reply. A short, natural bridge line is fine; "
            "do not make a fuss about it."
        )
    return (
        f"{opening} The transcript above was spoken in your previous role; from now on you are "
        "the person described at the top of this prompt, and only its catalog, prices and "
        f"policies apply. What you know about the caller still stands. {ask}"
    )
