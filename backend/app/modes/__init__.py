"""Which business Zuno is selling for on this call.

Two modes, one agent:

* "apple"   - the original product: Apple devices for businesses and
              individuals. The default, and unchanged by any of this.
* "perfume" - a beauty advisor for a luxury boutique that carries Dior beauty:
              fragrance first, then makeup and skincare. A demo persona, not
              affiliated with Dior.

The mode lives on the session (SessionState.mode) and everything that differs
between the two reads it from there on the next turn: the persona prompt, the
tool descriptions, the catalog, the knowledge base, stock, negotiation limits,
CRM tagging and the console theme.

This module is deliberately import-light (no sessions, no settings at import
time) because the session model itself imports `Mode` from here.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Literal, get_args

Mode = Literal["apple", "perfume"]
MODES: tuple[str, ...] = get_args(Mode)
DEFAULT_MODE: Mode = "apple"

# Human labels, used in prompt notes and logs.
MODE_LABELS: dict[str, str] = {
    "apple": "Apple device sales",
    "perfume": "the beauty boutique (Dior beauty)",
}


def coerce_mode(value: str | None) -> Mode:
    """A valid mode, or the default. Used for settings and anything else read
    from outside the type system: a typo in DEFAULT_MODE should cost the wrong
    persona, not a call that cannot start."""
    text = (value or "").strip().lower()
    return text if text in MODES else DEFAULT_MODE  # type: ignore[return-value]


def default_mode() -> Mode:
    from app.config import get_settings

    return coerce_mode(get_settings().default_mode)


# What the caller says to switch. Written as "<keyword> mode" on purpose: the
# bare word "perfume" or "apple" turns up in ordinary conversation constantly
# ("I'd like a perfume for my wife", "we're an Apple shop"), and a persona that
# flips on a product mention would be a disaster mid-call. Requiring the word
# "mode" straight after the keyword is what keeps "my mode of payment" or "in
# fragrance, what mode..." from tripping it.
#
# Devanagari spellings are included because a Hindi call transcribes the
# phrase in that script ("डियोर मोड") as often as in Latin letters.
_PERFUME_WORDS = r"dior|d or|deor|perfumes?|fragrances?|डियोर|डायर|परफ्यूम|फ्रेगरेंस"
_APPLE_WORDS = r"apples?|एप्पल|ऐपल|एपल"
_MODE_WORD = r"(?:mode|मोड)"

_SWITCH_RE = re.compile(
    rf"(?<![\wऀ-ॿ])(?:(?P<perfume>{_PERFUME_WORDS})|(?P<apple>{_APPLE_WORDS}))\s+{_MODE_WORD}(?![\wऀ-ॿ])"
)

# "don't switch to Dior mode", "not apple mode" - a request NOT to switch must
# not switch. Checked over the few words before the match only, so a negation
# earlier in a long sentence does not cancel a real request at its end.
_NEGATIONS = {"not", "dont", "don't", "no", "never", "without", "stop", "exit", "leave", "quit"}
_NEGATION_WINDOW = 3


def _normalise(text: str) -> str:
    # Lowercase, fold the curly apostrophe ASR sometimes emits, and turn
    # hyphens and other punctuation into spaces so "Dior-mode" reads as
    # "dior mode". NFC rather than NFKD: Devanagari must keep its combining
    # marks.
    text = unicodedata.normalize("NFC", text or "").lower().replace("\u2019", "'")
    text = re.sub(r"[^\w\u0900-\u097F' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Clause breaks. The keyword and "mode" must sit in the same clause: "I love
# perfume. Mode of transport?" is two thoughts, not a request.
_CLAUSE_BREAK = re.compile(r"[.!?;,\u0964]+")


def detect_requested_mode(text: str | None) -> Mode | None:
    """The mode the caller just asked for, or None.

    When both appear ("switch from Apple mode to Dior mode") the LAST request
    wins, because that is where the sentence ends up.
    """
    raw = text or ""
    if "mode" not in raw.lower() and "मोड" not in raw:
        return None

    negations = {n.replace("'", "") for n in _NEGATIONS}
    requested: Mode | None = None
    for clause in _CLAUSE_BREAK.split(raw):
        normalised = _normalise(clause)
        for match in _SWITCH_RE.finditer(normalised):
            before = normalised[: match.start()].split()[-_NEGATION_WINDOW:]
            if any(word.replace("'", "") in negations for word in before):
                continue
            requested = "perfume" if match.group("perfume") else "apple"
    return requested
