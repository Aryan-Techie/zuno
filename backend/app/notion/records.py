"""ZUNO records -> Notion property values and page bodies.

Pure functions, no I/O, shared by the setup seed and the live mirror so a
product written by either looks the same. Values are plain Python here;
schema.build_properties encodes them. Relation values are lists of Notion
page ids, which only the callers can resolve.

Titles are what Graphify labels nodes with, so they are written to read well
as a label: "Call · Jane Doe · 25 Nov", not a session uuid.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.notion import blocks
from app.notion.catalog import BRAND_INFO, PLAYBOOK_GUIDANCE
from app.notion.schema import LEAD_STAGES, TITLE, slugify, zuno_id


def _short(value: Any, limit: int = 80) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _when_label(value: Any) -> str:
    moment = _parse_dt(value) or datetime.now(timezone.utc)
    return f"{moment.day} {moment:%b %H:%M}"


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


# --- catalog ---------------------------------------------------------------


def brand_values(name: str, mode: str) -> dict[str, Any]:
    website, about = BRAND_INFO.get(slugify(name), (None, None))
    return {TITLE: name, "Mode": mode, "Website": website, "About": about}


def brand_body(name: str) -> list[dict]:
    _, about = BRAND_INFO.get(slugify(name), (None, None))
    return [blocks.paragraph(blocks.text(about or f"{name} products in the ZUNO catalog."))]


def family_values(name: str) -> dict[str, Any]:
    return {TITLE: name}


def family_body(name: str) -> list[dict]:
    return [blocks.paragraph(blocks.text(f"Olfactory family. Fragrances in the {name} family link here."))]


def note_values(name: str, tiers: list[str]) -> dict[str, Any]:
    return {TITLE: name, "Tiers": tiers}


def note_body(name: str) -> list[dict]:
    return [
        blocks.paragraph(
            blocks.text(f"Fragrance note. Every fragrance with {name} in its pyramid links here, by tier.")
        )
    ]


def playbook_values(topic: str) -> dict[str, Any]:
    return {
        TITLE: f"{topic.capitalize()} objections",
        "Topic": topic,
        "Guidance": PLAYBOOK_GUIDANCE.get(topic),
    }


def playbook_body(topic: str) -> list[dict]:
    guidance = PLAYBOOK_GUIDANCE.get(topic) or f"How ZUNO handles {topic} objections."
    return [
        blocks.paragraph(blocks.text(guidance)),
        blocks.heading("Answers that worked", 3),
        blocks.paragraph(
            blocks.text("ZUNO adds a line here, linked to the product, each time one of these is resolved on a call.")
        ),
    ]


def _price(product: dict) -> tuple[float | None, str | None]:
    if product.get("price_hkd_from") is not None:
        return product["price_hkd_from"], "HKD"
    if product.get("price_usd_from") is not None:
        return product["price_usd_from"], "USD"
    return None, None


def _sizes(product: dict) -> str:
    parts = []
    for size in product.get("sizes") or []:
        if not isinstance(size, dict):
            continue
        label = size.get("label") or ""
        if size.get("price_hkd") is not None:
            label += f" HK${size['price_hkd']:,}"
        elif size.get("price_usd") is not None:
            label += f" US${size['price_usd']:,}"
        if label.strip():
            parts.append(label.strip())
    return " · ".join(parts)


def product_values(
    product: dict,
    mode: str,
    *,
    brand: str | None = None,
    families: list[str] | None = None,
    notes: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """`brand`, `families` and `notes` (tier -> ids) are Notion page ids."""
    price, currency = _price(product)
    notes = notes or {}
    values: dict[str, Any] = {
        TITLE: product.get("name"),
        "Mode": mode,
        "Category": product.get("category"),
        "Line": product.get("line"),
        "Gender": product.get("gender"),
        "Subcategory": product.get("subcategory"),
        "Price from": price,
        "Currency": currency,
        "Sizes": _sizes(product) or None,
        "Stock": product.get("stock"),
        "Product page": product.get("url"),
        "Image": product.get("image_url"),
        "Description": product.get("description"),
        "Brand": [brand] if brand else None,
        "Families": families or None,
    }
    for tier, prop in (("top", "Top notes"), ("heart", "Heart notes"), ("base", "Base notes")):
        if notes.get(tier):
            values[prop] = notes[tier]
    return values


def product_body(product: dict) -> list[dict]:
    body = [blocks.paragraph(blocks.text(product.get("description") or product.get("name") or "Product"))]
    ingredients = [str(i) for i in product.get("key_ingredients") or [] if i]
    if ingredients:
        body.append(blocks.paragraph(blocks.text("Key ingredients: " + ", ".join(ingredients))))
    if product.get("url"):
        body.append(blocks.paragraph(blocks.text("Product page", url=product["url"])))
    return body


# --- calls and people ------------------------------------------------------


def lead_key(lead: dict | None, session_id: str | None) -> str:
    if lead and lead.get("id"):
        return zuno_id("lead", lead["id"])
    return zuno_id("lead", "session", session_id or "unknown")


def lead_label(lead: dict | None) -> str | None:
    if not lead:
        return None
    name = _short(lead.get("name"), 60)
    company = _short(lead.get("company"), 60)
    if name and company:
        return f"{name} ({company})"
    return name or company or None


def lead_values(lead: dict, mode: str | None, session_id: str | None) -> dict[str, Any]:
    pain = lead.get("pain_points") or []
    return {
        TITLE: lead_label(lead) or f"Caller {str(session_id or '')[:8]}".strip(),
        "Stage": LEAD_STAGES.get(str(lead.get("status") or ""), None),
        "Mode": mode,
        "Company": lead.get("company"),
        "Role": lead.get("title"),
        "Industry": lead.get("industry"),
        "Email": lead.get("email"),
        "Phone": lead.get("phone"),
        "Seats": lead.get("user_count"),
        "Budget": lead.get("budget_range"),
        "Timeline": lead.get("timeline"),
        "Decision stage": (lead.get("decision_stage") or "").replace("_", " ") or None,
        "Pain points": "; ".join(str(p) for p in pain) if pain else None,
        "Outcome": lead.get("outcome"),
    }


def lead_body(mode: str | None) -> list[dict]:
    where = f"a {mode} mode call" if mode else "a call"
    return [blocks.paragraph(blocks.text(f"Captured by ZUNO on {where}. Calls, meetings and objections link here."))]


def call_key(session_id: str | None) -> str:
    return zuno_id("call", session_id or "unknown")


def call_title(who: str | None, started: Any = None) -> str:
    return f"Call · {who or 'Unknown caller'} · {_when_label(started)}"


def call_body(mode: str | None) -> list[dict]:
    lead_in = f"ZUNO call in {mode} mode." if mode else "ZUNO call."
    return [blocks.paragraph(blocks.text(f"{lead_in} The wrap-up is added here when it ends."))]


def call_summary_values(summary: dict | None, outcome: str | None, mode: str | None) -> dict[str, Any]:
    summary = summary or {}
    result = outcome or summary.get("outcome")
    return {
        "Mode": mode,
        "Outcome": str(result).replace("_", " ") if result else None,
        "Headline": summary.get("headline") or None,
        "Next step": summary.get("recommended_action") or None,
        "Urgency": (summary.get("urgency") or "").replace("_", " ") or None,
        "Duration (s)": summary.get("duration_seconds") or None,
    }


def call_summary_body(summary: dict | None, outcome: str | None) -> list[dict]:
    summary = summary or {}
    body = [blocks.heading("Wrap-up", 3)]
    result = (outcome or summary.get("outcome") or "").replace("_", " ")
    headline = summary.get("headline") or ""
    body.append(blocks.paragraph(blocks.text(" - ".join(p for p in (result.capitalize(), headline) if p) or "Call ended.")))
    if summary.get("recommended_action"):
        body.append(blocks.paragraph(blocks.text("Do next: ", bold=True), blocks.text(summary["recommended_action"])))
    for title, key in (
        ("What they need", "facts"),
        ("What was agreed", "agreed"),
        ("What we owe them", "owed"),
        ("Risks", "risks"),
    ):
        items = [str(i) for i in summary.get(key) or [] if i]
        if items:
            body.append(blocks.paragraph(blocks.text(title, bold=True)))
            body.extend(blocks.bullet(blocks.text(i)) for i in items[:20])
    return body


def objection_key(session_id: str | None, objection: dict) -> str:
    if objection.get("id"):
        return zuno_id("objection", objection["id"])
    raised = " ".join(str(objection.get("raised_text") or "").lower().split())
    digest = hashlib.sha1(raised.encode()).hexdigest()[:8]
    return zuno_id("objection", session_id or "unknown", objection.get("topic") or "other", digest)


def objection_values(objection: dict, mode: str | None) -> dict[str, Any]:
    topic = str(objection.get("topic") or "other")
    raised = objection.get("raised_text") or ""
    return {
        TITLE: f"{topic.capitalize()}: {_short(raised, 70) or 'objection'}",
        "Status": "Resolved" if objection.get("resolved") else "Open",
        "Topic": topic,
        "Customer said": raised or None,
        "Answer": objection.get("resolution_text") or None,
        "Attempts": objection.get("attempts"),
        "Mode": mode,
    }


def objection_body(objection: dict) -> list[dict]:
    raised = objection.get("raised_text") or "Objection raised on a call."
    return [blocks.paragraph(blocks.text("Customer said: ", bold=True), blocks.text(str(raised)))]


def meeting_key(booking: dict, session_id: str | None) -> str:
    ident = booking.get("id") or booking.get("slot_id") or session_id or "unknown"
    return zuno_id("meeting", ident)


def _booking_times(booking: dict) -> tuple[Any, Any]:
    slot = booking.get("slot") if isinstance(booking.get("slot"), dict) else {}
    start = booking.get("start") or booking.get("slot_start") or slot.get("start")
    end = booking.get("end") or booking.get("slot_end") or slot.get("end")
    return start, end


def meeting_values(booking: dict, mode: str | None, who: str | None) -> dict[str, Any]:
    start, end = _booking_times(booking)
    slot = booking.get("slot") if isinstance(booking.get("slot"), dict) else {}
    rep = booking.get("rep_name") or booking.get("rep") or slot.get("rep_name")
    return {
        TITLE: f"Meeting · {who or 'Lead'} · {_when_label(start)}" if start else f"Meeting · {who or 'Lead'}",
        "When": {"start": start, "end": end} if start else None,
        "Rep": rep,
        "Status": "cancelled" if booking.get("cancelled_at") else "booked",
        "Mode": mode,
    }


def meeting_body(booking: dict, who: str | None) -> list[dict]:
    start, _ = _booking_times(booking)
    when = f" for {start}" if start else ""
    return [blocks.paragraph(blocks.text(f"Follow-up with {who or 'the lead'}{when}, booked by ZUNO on the call."))]
