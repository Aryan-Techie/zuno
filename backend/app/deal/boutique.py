"""Negotiation in perfume mode: luxury houses do not discount.

The Apple ladder (engine.py) exists because a B2B fleet deal is negotiated -
volume tiers, a desk that trades points for commitments, a human signature
past ten percent. A luxury beauty boutique is the opposite. Prices are fixed,
asking for a discount on a bottle of perfume is met with grace and something
complimentary, and the only real exception is a company buying gifts in bulk.

So the rules here are few and enforced in code, the same way engine.authorise
enforces the Apple floors - the prompt asks nicely, this makes it true:

* an individual purchase never gets a percentage, whatever was asked and
  whatever the model passed; the reply steers to complimentary extras;
* a corporate gifting order of CORPORATE_MIN_UNITS or more may get up to
  CORPORATE_MAX_DISCOUNT_PCT, signed by the boutique's deal desk (the manager),
  and only against a single confirmed order;
* nothing ever goes past that cap - there is no human escalation path for a
  bigger number, because there is no bigger number to approve.

No model call: the desk here is a rule, so this adds no latency to the turn.
Prices come from the perfume catalog (HK$), never from the model.
"""
from __future__ import annotations

from app.catalogs import catalog
from app.deal.models import Commitment, Concession, DeviceLine, Offer, Quote

CORPORATE_MIN_UNITS = 10
CORPORATE_MAX_DISCOUNT_PCT = 5.0

# The boutique's complimentary extras - every one of them is in the demo
# boutique FAQ (app/rag/docs_perfume/boutique_faq.md), so what she offers here
# is what the knowledge base will confirm if she is asked about it.
EXTRAS: tuple[Concession, ...] = (
    Concession(kind="bundle", detail="Two complimentary deluxe samples, chosen to suit their taste"),
    Concession(kind="bundle", detail="Complimentary gift wrapping with a handwritten message card"),
    Concession(kind="bundle", detail="Complimentary engraving on eligible bottles of 100 ml and above"),
    Concession(kind="bundle", detail="Complimentary delivery across Hong Kong on orders of HK$800 or more"),
)
CORPORATE_EXTRAS: tuple[Concession, ...] = (
    Concession(kind="bundle", detail="Individual gift wrapping and a message card for every recipient"),
    Concession(kind="bundle", detail="A dedicated advisor and delivery to each recipient across Hong Kong"),
)


def _hkd(amount: float) -> str:
    return f"HK${amount:,.0f}"


def _lines(tool_input: dict, session) -> list[DeviceLine]:
    """Priced lines from the catalog. Each entry the model passes is resolved
    to a real catalog row and size; anything that does not resolve is left
    out rather than priced at a guess."""
    lines: list[DeviceLine] = []
    for entry in tool_input.get("device_mix") or []:
        quantity = int(entry.get("quantity") or 0)
        if quantity <= 0:
            continue
        named = str(entry.get("model", ""))
        product, _ = catalog.find(named, "perfume")
        if product is None:
            continue
        size = catalog.pick_size(product, named)
        price = catalog.price_of(size, product)
        if price is None:
            continue
        label = product["name"] + (f" {size['label']}" if size and size.get("label") else "")
        lines.append(DeviceLine(model_key=product["id"], label=label, quantity=quantity, list_unit_price=price))

    if not lines and session.spotlight and session.spotlight.get("category"):
        # Nothing named: the product on screen is what they are talking about.
        product = catalog.get(session.spotlight["id"], "perfume")
        if product is not None:
            size = catalog.pick_size(product, tool_input.get("customer_ask"))
            price = catalog.price_of(size, product)
            if price is not None:
                units = session.left_brain.user_count or 1
                label = product["name"] + (f" {size['label']}" if size and size.get("label") else "")
                lines.append(
                    DeviceLine(model_key=product["id"], label=label, quantity=units, list_unit_price=price)
                )
    return lines


def _quote(lines: list[DeviceLine], units: int, granted_pct: float) -> Quote:
    list_total = sum(line.quantity * line.list_unit_price for line in lines)
    effective_total = list_total * (1 - granted_pct / 100.0)
    return Quote(
        units=units,
        lines=lines,
        list_unit_price=round(list_total / units, 2) if units and lines else 0.0,
        list_total=round(list_total, 2),
        tier_name="Corporate gifting" if granted_pct else "Boutique",
        volume_discount_pct=0.0,
        negotiated_discount_pct=granted_pct,
        effective_unit_price=round(effective_total / units, 2) if units and lines else 0.0,
        effective_total=round(effective_total, 2),
        total_savings=round(list_total - effective_total, 2),
    )


def _price_summary(quote: Quote, corporate: bool) -> str:
    if not quote.lines:
        return (
            "No product has been priced yet. Prices are fixed at the boutique - quote them from "
            "search_pricing_rag or check_inventory, in Hong Kong dollars."
        )
    mix = ", ".join(f"{line.quantity} x {line.label}" for line in quote.lines)
    if quote.units == 1 and len(quote.lines) == 1:
        text = f"{mix} is {_hkd(quote.list_total)}, the boutique's fixed price."
    else:
        text = f"{mix}: {_hkd(quote.list_total)} at the boutique's fixed prices."
    if quote.negotiated_discount_pct:
        text += (
            f" With {quote.negotiated_discount_pct:g}% corporate gifting pricing that comes to "
            f"{_hkd(quote.effective_total)}, a saving of {_hkd(quote.total_savings)}."
        )
    elif corporate:
        text += " Corporate gifting pricing has not been applied."
    return text


def authorise(
    *, requested_pct: float | None, units: int, corporate: bool, already_granted: float
) -> tuple[float, str, bool, str | None]:
    """(granted_pct, authorised_by, clamped, clamp_reason). The whole policy."""
    requested = max(0.0, float(requested_pct or 0.0))
    if not corporate or units < CORPORATE_MIN_UNITS:
        reason = None
        if requested > 0:
            reason = (
                "the boutique does not discount individual purchases; complimentary extras offered instead"
                if not corporate
                else f"corporate gifting pricing starts at {CORPORATE_MIN_UNITS} pieces; this order is {units}"
            )
        return 0.0, "zuno", requested > 0, reason

    # A corporate order that did not name a number is offered the cap: the
    # boutique has one corporate price, not an opening bid to haggle up from.
    wanted = requested if requested_pct is not None else CORPORATE_MAX_DISCOUNT_PCT
    granted = min(max(wanted, already_granted), CORPORATE_MAX_DISCOUNT_PCT)
    clamped = wanted > CORPORATE_MAX_DISCOUNT_PCT
    reason = (
        f"asked for {wanted:g}%; corporate gifting pricing is capped at {CORPORATE_MAX_DISCOUNT_PCT:g}%"
        if clamped
        else None
    )
    return round(granted, 2), "deal_desk", clamped, reason


def negotiate(tool_input: dict, session) -> dict:
    """The perfume-mode negotiate_deal. Same result shape as the Apple one, so
    the pipeline, the console's deal panel and the wrap-up need no branch."""
    from app.crm import service as crm_service
    from app.deal import engine

    negotiation = session.negotiation
    lines = _lines(tool_input, session)
    units = sum(line.quantity for line in lines) or int(session.left_brain.user_count or 1)
    corporate = bool(tool_input.get("corporate_gifting")) or bool(session.left_brain.company)

    requested_pct = tool_input.get("requested_discount_pct")
    list_quote = _quote(lines, units, 0.0)
    if requested_pct is None and tool_input.get("target_total_price") and list_quote.list_total:
        requested_pct = engine.discount_for_target(list_quote, float(tool_input["target_total_price"]))
    if requested_pct is None and tool_input.get("target_unit_price") and list_quote.list_total:
        requested_pct = engine.discount_for_target(
            list_quote, float(tool_input["target_unit_price"]) * units
        )
    requested_pct = float(requested_pct) if requested_pct is not None else None

    granted, authorised_by, clamped, clamp_reason = authorise(
        requested_pct=requested_pct,
        units=units,
        corporate=corporate,
        already_granted=negotiation.granted_discount_pct,
    )
    eligible = corporate and units >= CORPORATE_MIN_UNITS
    quote = _quote(lines, units, granted)

    concessions = list(EXTRAS) + (list(CORPORATE_EXTRAS) if eligible else [])
    if granted > 0:
        concessions.insert(
            0,
            Concession(
                kind="discount",
                detail=f"{granted:g}% corporate gifting pricing on this order",
                discount_pct=granted,
            ),
        )
    commitments = (
        [
            Commitment(kind="single_po", detail="Confirm it as one order, on one invoice."),
            Commitment(kind="decision_by", detail="Agree the date they will confirm the order by."),
        ]
        if granted > 0
        else []
    )

    round_number = negotiation.round_count + 1
    offer = Offer(
        round=round_number,
        customer_ask=tool_input.get("customer_ask", ""),
        requested_discount_pct=requested_pct,
        quote=quote,
        granted_discount_pct=granted,
        concessions=concessions,
        commitments=commitments,
        authorised_by=authorised_by,
        clamped=clamped,
        clamp_reason=clamp_reason,
        declined=False,
        rationale=(
            "Corporate gifting order: capped corporate pricing against a single confirmed order."
            if granted > 0
            else "Boutique prices are fixed; complimentary extras instead of a discount."
        ),
        price_summary=_price_summary(quote, corporate),
    )
    negotiation.rounds.append(offer)
    negotiation.granted_discount_pct = granted

    crm_service.add_note(
        session.session_id,
        f"Boutique round {round_number}: asked {requested_pct if requested_pct is not None else 'unspecified'}"
        f" -> granted {granted:g}% ({authorised_by})"
        + (f"; {clamp_reason}" if clamp_reason else ""),
    )

    if granted > 0:
        guidance = (
            f"This is a corporate gifting order, so {granted:g}% corporate pricing is authorised - "
            "the most the boutique gives. Read price_summary as written, mention the gifting "
            "extras, and ask for what is in ask_for_in_return in the same breath. Never go higher."
        )
    elif eligible:
        guidance = (
            "Corporate pricing is available but not yet applied. Read price_summary, then offer the "
            "complimentary extras and ask whether they would like to confirm the order."
        )
    else:
        guidance = (
            "No discount - luxury houses do not discount, and neither does this boutique. Say it "
            "warmly and without apologising, never as a flat no. In the same breath offer the "
            "complimentary extras in offer_concessions and ask which would make it special: "
            "the samples, the gift wrap, the engraving. Do NOT invent a percentage, a promo code "
            "or a price match. If they are buying ten or more as corporate gifts, say corporate "
            "gifting pricing exists and ask about the order."
        )

    return {
        "price_summary": offer.price_summary,
        "granted_discount_pct": granted,
        "authorised_by": authorised_by,
        "offer_concessions": [c.detail for c in concessions],
        "ask_for_in_return": [c.detail for c in commitments],
        "desk_read": "Asking about price at a luxury counter is usually about value, not the number.",
        "awaiting_human_approval": False,
        "currency": "HKD",
        "corporate_gifting_eligible": eligible,
        "guidance": guidance,
    }
