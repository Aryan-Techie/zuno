"""Catalog files -> the reference pages the graph hangs off.

Reads backend/app/catalogs/{apple,perfume}.json directly (the shared contract
format) rather than going through the runtime catalog module, so the setup
script works with whichever files exist and the mirror does not depend on how
the call loop chooses to cache them.

Brands, olfactory families and fragrance notes are not in the catalog as
records of their own; they are derived here from the products, keyed by slug
so "Calabrian Bergamot" and "calabrian bergamot" are one node, not two.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.notion.schema import OBJECTION_TOPICS, slugify, zuno_id

logger = logging.getLogger("zuno.notion")

CATALOG_DIR = Path(__file__).resolve().parent.parent / "catalogs"
CATALOG_FILES = {"apple": "apple.json", "perfume": "perfume.json"}
NOTE_TIERS = ("top", "heart", "base")

BRAND_INFO = {
    "apple": ("https://www.apple.com", "Macs, iPhones, iPads and accessories for teams and individuals."),
    "dior": ("https://www.dior.com", "Dior beauty: fragrance first, then makeup and skincare."),
}

PLAYBOOK_GUIDANCE = {
    "pricing": (
        "Price pushback. Anchor on value per seat or per wear before discounting, "
        "and only move on price through the deal desk."
    ),
    "trust": (
        "Doubt about the seller, warranty, authenticity or support. Answer with "
        "specifics: policies, guarantees, a named human follow-up."
    ),
    "product": (
        "Doubt that the product fits: specs, compatibility, scent, longevity. "
        "Answer from the catalog and offer the closest alternative."
    ),
}


def load_catalogs(catalog_dir: Path = CATALOG_DIR) -> dict[str, list[dict]]:
    """Mode -> products, for whichever catalog files exist and parse."""
    out: dict[str, list[dict]] = {}
    for mode, filename in CATALOG_FILES.items():
        path = catalog_dir / filename
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("catalog %s is unreadable, skipping it", path.name)
            continue
        if isinstance(data, dict):
            data = data.get("products", [])
        out[mode] = [p for p in data if isinstance(p, dict) and p.get("id") and p.get("name")]
    return out


def mode_for(product: dict, default: str | None = None) -> str:
    if default and default in CATALOG_FILES:
        return default
    return "apple" if str(product.get("brand", "")).lower() == "apple" else "perfume"


def brand_key(product: dict) -> str | None:
    brand = str(product.get("brand") or "").strip()
    return zuno_id("brand", slugify(brand)) if brand else None


def family_names(product: dict) -> list[str]:
    """A product's olfactory families. The catalog sometimes lists several in
    one string ("Floral, Vanilla, Sensual"); each is its own family page, so
    every floral fragrance meets at the same Floral node."""
    raw = str(product.get("family") or "")
    names: list[str] = []
    for part in re.split(r"[,/;]|\band\b", raw):
        name = _display(" ".join(part.split()))
        if name and slugify(name) not in {slugify(n) for n in names}:
            names.append(name)
    return names


def family_key(name: str) -> str:
    return zuno_id("family", slugify(name))


def note_names(product: dict) -> dict[str, list[str]]:
    """Tier -> note display names, for a fragrance with a pyramid."""
    notes = product.get("notes")
    if not isinstance(notes, dict):
        return {}
    out: dict[str, list[str]] = {}
    for tier in NOTE_TIERS:
        names = [str(n).strip() for n in notes.get(tier) or [] if str(n).strip()]
        if names:
            out[tier] = names
    return out


def note_key(name: str) -> str:
    return zuno_id("note", slugify(name))


def _display(name: str) -> str:
    return name[:1].upper() + name[1:] if name else name


@dataclass
class SeedPlan:
    brands: dict[str, dict] = field(default_factory=dict)
    families: dict[str, dict] = field(default_factory=dict)
    notes: dict[str, dict] = field(default_factory=dict)
    playbook: dict[str, dict] = field(default_factory=dict)
    # Each entry is a catalog product with "_mode" added.
    products: list[dict] = field(default_factory=list)

    def page_count(self) -> int:
        return (
            len(self.brands) + len(self.families) + len(self.notes) + len(self.playbook) + len(self.products)
        )

    def counts(self) -> dict[str, int]:
        return {
            "brands": len(self.brands),
            "families": len(self.families),
            "notes": len(self.notes),
            "playbook": len(self.playbook),
            "products": len(self.products),
        }


def _priority(product: dict) -> int:
    # Fragrances first: they carry the notes and families that make the
    # catalog a graph rather than a list. Then devices, then the rest. The
    # sort is stable, so catalog order decides within each group.
    category = str(product.get("category") or "")
    return 0 if category == "fragrance" else 1 if product.get("_mode") == "apple" else 2


def build_seed(
    catalogs: dict[str, list[dict]],
    *,
    modes: tuple[str, ...] = ("apple", "perfume"),
    max_products: int | None = None,
    max_pages: int | None = None,
    reserve_pages: int = 0,
) -> SeedPlan:
    """Pick the products to seed and derive their brand/family/note pages.

    max_pages is a budget for the whole seed (Graphify's Free web plan syncs
    100 pages), with reserve_pages kept free for the leads, calls and
    objections live calls will add. Products are taken in priority order
    while what they bring along still fits.
    """
    candidates = [
        {**p, "_mode": mode} for mode in modes for p in catalogs.get(mode, [])
    ]
    if max_pages is not None:
        candidates.sort(key=_priority)
    if max_products is not None:
        per_mode: dict[str, int] = {}
        kept = []
        for product in candidates:
            if per_mode.get(product["_mode"], 0) < max_products:
                kept.append(product)
                per_mode[product["_mode"]] = per_mode.get(product["_mode"], 0) + 1
        candidates = kept

    plan = SeedPlan()
    for topic in OBJECTION_TOPICS:
        plan.playbook[zuno_id("playbook", topic)] = {"topic": topic}
    budget = None if max_pages is None else max(0, max_pages - reserve_pages - 2)
    seen_ids: set[str] = set()

    for product in candidates:
        if product["id"] in seen_ids:
            continue
        new_brand = {}
        bkey = brand_key(product)
        if bkey and bkey not in plan.brands:
            new_brand[bkey] = {"name": str(product["brand"]).strip(), "mode": product["_mode"]}
        new_family = {}
        for name in family_names(product):
            fkey = family_key(name)
            if fkey not in plan.families:
                new_family[fkey] = {"name": name}
        new_notes: dict[str, dict] = {}
        known_tiers: list[tuple[str, str]] = []
        for tier, names in note_names(product).items():
            for name in names:
                key = note_key(name)
                if key in plan.notes:
                    known_tiers.append((key, tier))
                elif key in new_notes:
                    if tier not in new_notes[key]["tiers"]:
                        new_notes[key]["tiers"].append(tier)
                else:
                    new_notes[key] = {"name": _display(name), "tiers": [tier]}
        cost = 1 + len(new_brand) + len(new_family) + len(new_notes)
        if budget is not None and plan.page_count() + cost > budget:
            continue
        plan.brands.update(new_brand)
        plan.families.update(new_family)
        plan.notes.update(new_notes)
        for key, tier in known_tiers:
            if tier not in plan.notes[key]["tiers"]:
                plan.notes[key]["tiers"].append(tier)
        plan.products.append(product)
        seen_ids.add(product["id"])
    return plan


class CatalogIndex:
    """Lazy id -> product lookup for the mirror, re-read once on a miss
    because the catalog files can be regenerated while the backend runs."""

    def __init__(self, catalog_dir: Path = CATALOG_DIR) -> None:
        self._dir = catalog_dir
        self._lock = threading.Lock()
        self._by_id: dict[str, dict] | None = None

    def _load(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for mode, products in load_catalogs(self._dir).items():
            for product in products:
                out[product["id"]] = {**product, "_mode": mode}
        return out

    def get(self, product_id: str) -> dict[str, Any] | None:
        with self._lock:
            if self._by_id is None or product_id not in self._by_id:
                self._by_id = self._load()
            return self._by_id.get(product_id)
