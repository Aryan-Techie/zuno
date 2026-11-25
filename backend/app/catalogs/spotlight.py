"""The product card on the customer's screen.

Two things put a product there:

* the model, by calling show_product while it talks about something specific;
* the caller's (or Zuno's) own words, matched against the current mode's
  catalog aliases - deterministic, so naming "Sauvage" puts Sauvage on screen
  without spending a model hop on it.

Both go through `mark`, which is the one rule: a product is put on screen at
most once per COOLDOWN_SECONDS. Without it the card would re-announce itself
on every hop of a turn that keeps saying the product's name.
"""
from __future__ import annotations

import time

from app import bus_events
from app.catalogs import catalog

COOLDOWN_SECONDS = 20.0


def mark(session, product: dict, *, now: float | None = None) -> bool:
    """Make `product` the spotlight. Returns whether it is newly shown, i.e.
    whether the console and the integrations should hear about it."""
    now = time.time() if now is None else now
    product_id = product["id"]
    last = session.spotlight_shown_at.get(product_id)
    if last is not None and now - last < COOLDOWN_SECONDS:
        return False
    session.spotlight_shown_at[product_id] = now
    session.spotlight = product
    if product_id not in session.products_mentioned:
        session.products_mentioned.append(product_id)
    return True


def publish(session, product: dict, publisher) -> None:
    """Tell the console and the integrations. Both are off the turn path: the
    publisher appends to the session's event log (plus a backgrounded RTM
    post when configured) and the bus runs on its own pool."""
    publisher.publish(session.session_id, "product_spotlight", {"product": product})
    bus_events.emit("product_spotlighted", session, product=product)


def from_text(session, text: str | None, publisher, *, now: float | None = None) -> dict | None:
    """Spotlight whatever catalog product `text` names, if any and if it is
    not already on screen. Returns the product when it was newly shown."""
    product = catalog.match_alias(text, session.mode)
    if product is None:
        return None
    if not mark(session, product, now=now):
        return None
    publish(session, product, publisher)
    return product
