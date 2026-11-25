from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.deal.models import NegotiationState
from app.escalation.models import TranscriptTurn
from app.memory.schema import LeftBrain, RightBrain
from app.modes import Mode, default_mode

SessionStatus = Literal["active", "ended", "escalated"]
Outcome = Literal["meeting_booked", "escalated", "qualified", "disqualified", "follow_up"]


class SessionState(BaseModel):
    session_id: str
    agora_channel: str | None = None
    agent_id: str | None = None

    crm_lead_id: str | None = None
    booking_id: str | None = None
    # Kept alongside booking_id because the call-end confirmation pass needs
    # the slot's time and rep, and neither calendar store can look a booking
    # back up by its id - availability in the EspoCRM one is derived, not
    # stored as rows.
    booking_slot_id: str | None = None
    # Set only after a confirmation email has actually left the building, so
    # the call-end backstop retries a send that failed at booking time and
    # skips one that did not. See notify/service.py.
    confirmation_sent: bool = False
    mem0_user_id: str | None = None  # defaults to session_id once memory (Step 4) is wired in

    # Which business this call is selling for - see app/modes/. Read fresh on
    # every turn (and every hop) rather than cached anywhere, so a switch said
    # out loud or clicked on the console takes effect on the very next model
    # call.
    mode: Mode = Field(default_factory=default_mode)
    # Set when the console switches mode, consumed by the next turn's prompt
    # so the reply picks up the new persona with a bridge rather than as if
    # nothing had happened. A voice switch does not need it: the turn that
    # heard it is the turn that answers it.
    pending_mode_switch: dict | None = None
    # The catalog entry currently on the customer's screen (the console's
    # product spotlight), or None. A whole CatalogProduct, not an id, so the
    # events endpoint can hand it straight to the browser.
    spotlight: dict | None = None
    # product id -> epoch seconds it was last put on screen. The spotlight
    # fires from the caller's words and from the model's show_product tool;
    # this is what keeps the two from flashing the same card twice in a row.
    spotlight_shown_at: dict[str, float] = Field(default_factory=dict)
    # Catalog ids that were put on screen during the call, in order and once
    # each - the "products" list in the call_ended integration event.
    products_mentioned: list[str] = Field(default_factory=list)

    status: SessionStatus = "active"
    outcome: Outcome | None = None

    transcript: list[TranscriptTurn] = Field(default_factory=list)
    # Append-only log of the same envelopes published to RTM, so the browser
    # can poll for them over plain HTTP (GET /api/session/{id}/events). RTM
    # delivery to the UI proved unreliable; the panels are cosmetic, so they
    # get a transport we fully control rather than one we cannot debug.
    events: list[dict] = Field(default_factory=list)
    # Every tool dispatched on this call, in order and with repeats. Kept
    # on the session rather than derived from `events`, because those only
    # land here when the RTM recorder is in the publisher chain - and what
    # work the agent did is not allowed to depend on whether credentials
    # for a UI side-channel happen to be configured.
    tool_calls: list[str] = Field(default_factory=list)
    # The voice Agora currently has for this call, so a switch that is
    # already in force is not bought a second time.
    current_voice_id: str | None = None
    left_brain: LeftBrain = Field(default_factory=LeftBrain)
    right_brain: RightBrain = Field(default_factory=RightBrain)
    # Every round of bargaining on this call, as authorised - not as the
    # deal desk proposed it. See app/deal/engine.py::authorise.
    negotiation: NegotiationState = Field(default_factory=NegotiationState)
    last_rag_score: float | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
