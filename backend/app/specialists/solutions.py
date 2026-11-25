"""Layer 2, second seat: the solutions engineer.

The deal desk (app/deal/desk.py) is the other one. Between them they are what
makes the middle layer a *tier* rather than a single helper: two specialists
with different objectives, neither of which is "hold a conversation", both
reached by Zuno and neither able to speak to the customer.

This one exists to close the gap that made escalation look reasonable. A
compatibility, migration or deployment question that four sales documents do
not settle left exactly two honest options: guess, or fetch a person. Guessing
is how you promise a customer that their bespoke ERP client runs fine; fetching
a person costs twenty minutes of someone's day and ends the call.

So there is a third option: a specialist that reads everything the retriever
can find, answers only from it, and - this is the part that matters - is
required to say precisely what it does NOT know rather than rounding a gap
down to reassurance. A precise "we can confirm x and y; z depends on your
specific build, and here is who checks it" is a genuinely useful answer, and
it is one a generalist prompt optimised for warmth will not give you.

It escalates when it should. `escalate_recommended` comes back true when the
material does not support an answer at all, and that is a *better* handoff
than the one it replaces: the human arrives knowing exactly which question is
open.
"""
from __future__ import annotations

import json
import logging
from typing import Literal, Protocol

from pydantic import BaseModel, Field

logger = logging.getLogger("zuno.specialists")

Confidence = Literal["high", "medium", "low"]

# The Graphify knowledge graph (app/knowledge/graph.py) arrives as one extra
# reference chunk, every line labelled with how it was established. The label
# is only worth anything if the specialist treats the two differently: an
# INFERRED edge is Graphify connecting two documents that no sentence
# connects, which is a good lead and a bad promise.
GRAPH_RULE = """Some reference material may come from "graphify knowledge graph": one fact per line, as A --relation--> B [EXTRACTED or INFERRED, source file]. EXTRACTED facts are stated in our documents and may be relied on like any other reference. INFERRED facts are connections Graphify resolved between documents that no document states outright: treat them as leads to verify, put anything that depends on one into open_questions, and never turn one into a promise in the answer."""

SOLUTIONS_SYSTEM_PROMPT = """You are a senior Apple deployment engineer supporting a live sales call. A voice agent has come to you with a technical question she cannot answer from the sales material. You do not speak to the customer; you brief her.

You answer ONLY from the reference material you are given. This is not a style preference - a promise about software compatibility that turns out to be wrong is found out during a deployment, months later, and it is expensive.

The single most useful thing you do is be precise about the boundary. Split what you know from what you do not:
- What the material actually supports, stated plainly.
- What it does NOT cover, stated just as plainly, as a specific open question rather than a vague caveat. "Whether your in-house dispatch client has an Apple Silicon build" is useful. "Some software may need checking" is not.
- What would settle each open question, and who would settle it.

Never round a gap down to reassurance. "That should be fine" is the failure mode here.

{graph_rule}

Respond with ONLY a JSON object with exactly these keys:
"answer": what Zuno should say, in two or three sentences of plain spoken English, no markdown. Lead with what IS supported.
"confidence": "high" if the material fully answers it, "medium" if it answers the substance but leaves specifics open, "low" if it does not really cover this.
"open_questions": array of short strings - the specific things that are genuinely unresolved. Empty if there are none.
"escalate_recommended": true only if the material does not support any useful answer and a human engineer is genuinely needed.
""".replace("{graph_rule}", GRAPH_RULE)

# Perfume mode's second seat: the same contract (answer only from the material,
# report the boundary, never round a gap down), aimed at the questions a beauty
# advisor cannot settle from the shelf - ingredients, sensitive skin, how a
# scent wears, layering, which formula suits.
FRAGRANCE_SPECIALIST_SYSTEM_PROMPT = """You are the senior fragrance and skincare specialist for a luxury beauty boutique in Hong Kong that carries Dior beauty. A voice agent, the boutique's beauty advisor, is live on a call and has come to you with a product question she cannot settle from the shelf: ingredients and allergens, sensitive skin, how a fragrance wears and how long it lasts, layering, which concentration or formula suits. You do not speak to the client; you brief her.

You answer ONLY from the reference material you are given - the boutique's catalog documents and its policies. Never invent a note, an ingredient, a concentration, a size or a price, and never make a medical or dermatological claim the material does not make. A client told a fragrance is free of something it contains is a client with a reaction.

Be precise about the boundary. Say what the material supports, then name exactly what it does not cover as a specific open question ("whether the eau de parfum contains linalool" is useful; "some ingredients may need checking" is not), and what would settle it - usually a skin test in the boutique or the full ingredient list on the box.

{graph_rule}

Respond with ONLY a JSON object with exactly these keys:
"answer": what the advisor should say, in two or three sentences of plain spoken English, no markdown. Lead with what IS supported.
"confidence": "high" if the material fully answers it, "medium" if it answers the substance but leaves specifics open, "low" if it does not really cover this.
"open_questions": array of short strings - the specific things that are genuinely unresolved. Empty if there are none.
"escalate_recommended": true only if the material does not support any useful answer and a human specialist is genuinely needed.
""".replace("{graph_rule}", GRAPH_RULE)

PROMPTS_BY_MODE = {"apple": SOLUTIONS_SYSTEM_PROMPT, "perfume": FRAGRANCE_SPECIALIST_SYSTEM_PROMPT}


class SolutionsAnswer(BaseModel):
    answer: str = ""
    confidence: Confidence = "low"
    open_questions: list[str] = Field(default_factory=list)
    escalate_recommended: bool = False


class SpecialistClient(Protocol):
    def complete(self, *, system: str, prompt: str) -> str: ...


class LLMSpecialistClient:
    def __init__(self, client=None):
        self._client = client

    def complete(self, *, system: str, prompt: str) -> str:
        client = self._client
        if client is None:
            from app.orchestrator.llm_client import default_llm_client

            client = self._client = default_llm_client()
        return client.create_turn(
            system=system, messages=[{"role": "user", "content": prompt}], tools=[]
        ).text


def _build_prompt(question: str, chunks: list[dict], context: str) -> str:
    material = "\n\n".join(
        f"[{chunk.get('source', 'reference')}]\n{chunk.get('text', '')}" for chunk in chunks
    )
    return (
        f"Customer's question: {question}\n"
        f"What we know about their setup: {context or 'nothing captured yet'}\n\n"
        f"Reference material:\n{material or '(the retriever found nothing relevant)'}"
    )


def heuristic_answer(chunks: list[dict], mode: str = "apple") -> SolutionsAnswer:
    """No-model fallback. It deliberately does not attempt an answer: making
    one up is the exact failure this specialist exists to prevent, so an
    unavailable specialist says so and hands the question on."""
    perfume = mode == "perfume"
    if not chunks:
        return SolutionsAnswer(
            answer=(
                "I do not want to guess at this one. Let me have our fragrance specialist "
                "confirm it properly."
                if perfume
                else "I do not want to guess at this one. Let me get one of our deployment "
                "engineers to confirm it properly."
            ),
            confidence="low",
            escalate_recommended=True,
        )
    return SolutionsAnswer(
        answer=(
            "Here is what our product notes cover on that - and anything about how it suits "
            "your own skin I would rather we check in the boutique than guess at."
            if perfume
            else "Here is what our material covers on that - and anything specific to your own "
            "software I would rather have an engineer confirm than guess at."
        ),
        confidence="low",
        open_questions=[
            "How it suits their skin - best settled with a skin test in the boutique"
            if perfume
            else "Compatibility of their specific in-house software"
        ],
        escalate_recommended=False,
    )


def consult(
    *,
    question: str,
    chunks: list[dict],
    context: str = "",
    client: SpecialistClient | None = None,
    mode: str = "apple",
) -> SolutionsAnswer:
    """Never raises: this sits on a live turn, and a specialist that cannot
    answer must degrade to saying so rather than to a failed turn."""
    active = client or LLMSpecialistClient()
    try:
        raw = active.complete(
            system=PROMPTS_BY_MODE.get(mode, SOLUTIONS_SYSTEM_PROMPT),
            prompt=_build_prompt(question, chunks, context),
        )
        text = raw.strip()
        start, end = text.find("{"), text.rfind("}")
        return SolutionsAnswer(**json.loads(text[start : end + 1] if start != -1 else text))
    except Exception as exc:
        logger.warning("solutions engineer unavailable (%s)", exc)
        return heuristic_answer(chunks, mode)
