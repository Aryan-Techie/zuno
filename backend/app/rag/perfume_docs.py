"""Turns the perfume catalog into the boutique's knowledge-base documents.

The retriever chunks markdown on level-1 and level-2 headings (ingest.py), so
the layout here is chosen for retrieval rather than for reading:

* one `#` section per olfactory family (or makeup/skincare type), carrying a
  one-line roll call of everything in it - that is the chunk that answers
  "what woody fragrances do you have";
* one `##` section per product, carrying its family, concentration, notes,
  sizes and HK$ prices in plain sentences - the chunk that answers "how much
  is the 100 ml Sauvage" and "does Miss Dior have rose in it".

Every fact is copied from the catalog row, never paraphrased into something
the row does not say: this is what Zuno quotes prices and notes from, and the
whole point of the perfume persona is that she never invents either.

Written by scripts/build_perfume_docs.py. boutique_faq.md in the same
directory is hand-written and is never touched by this module.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

GENERATED_FILES = ("fragrance.md", "makeup.md", "skincare.md")

_GENDER = {"women": "for women", "men": "for men", "unisex": "unisex"}


def _price(amount) -> str:
    return f"HK${amount:,.0f}" if isinstance(amount, (int, float)) else "price on request"


def _sizes_line(product: dict) -> str:
    sizes = [s for s in (product.get("sizes") or []) if isinstance(s, dict)]
    if not sizes:
        if product.get("price_hkd_from") is not None:
            return f"Price: from {_price(product['price_hkd_from'])}."
        return "Price: on request at the boutique."
    parts = [f"{s.get('label') or 'one size'} {_price(s.get('price_hkd'))}" for s in sizes]
    line = "Sizes and prices: " + ", ".join(parts) + "."
    if product.get("price_hkd_from") is not None and len(sizes) > 1:
        line += f" From {_price(product['price_hkd_from'])}."
    return line


def _notes_line(product: dict) -> str:
    notes = product.get("notes") or {}
    if not isinstance(notes, dict):
        return ""
    bits = []
    for tier, label in (("top", "Top notes"), ("heart", "Heart notes"), ("base", "Base notes")):
        values = [v for v in (notes.get(tier) or []) if v]
        if values:
            bits.append(f"{label}: {', '.join(values)}.")
    return " ".join(bits)


def _product_section(product: dict) -> str:
    brand = product.get("brand") or "Dior"
    lines = [f"## {product['name']} ({brand})"]

    kind = [product.get("category") or ""]
    if product.get("subcategory"):
        kind.append(product["subcategory"])
    descriptor = ", ".join(k for k in kind if k)
    gender = _GENDER.get(product.get("gender") or "")
    if gender:
        descriptor += f", {gender}"
    facts = [f"{product['name']} is a {brand} {descriptor}."]
    if product.get("family"):
        facts.append(f"Olfactory family: {product['family']}.")
    if product.get("line") and product["line"] != product["name"]:
        facts.append(f"Part of the {product['line']} line.")
    lines.append(" ".join(facts))

    notes = _notes_line(product)
    if notes:
        lines.append(notes)
    if product.get("key_ingredients"):
        lines.append("Key ingredients: " + ", ".join(product["key_ingredients"]) + ".")
    if product.get("description"):
        lines.append(product["description"].strip())
    lines.append(_sizes_line(product))
    lines.append(f"Catalog id: {product['id']}.")
    return "\n".join(lines)


def _group(products: list[dict], key, fallback: str) -> "OrderedDict[str, list[dict]]":
    groups: OrderedDict[str, list[dict]] = OrderedDict()
    for product in products:
        groups.setdefault((key(product) or fallback).strip() or fallback, []).append(product)
    return OrderedDict(sorted(groups.items(), key=lambda item: item[0].lower()))


def _render(title: str, intro: str, groups, heading) -> str:
    # No "generated file" banner: the chunker would make it a chunk of its
    # own, and a dozen words in a tiny chunk outscore real content on TF-IDF
    # ("do you do engraving" matched the banner's "Do not edit"). The module
    # docstring and the build script say where these files come from.
    out = [f"# {title}", "", intro]
    for name, members in groups.items():
        roll_call = "; ".join(
            f"{p['name']}" + (f" ({_GENDER[p['gender']]})" if p.get("gender") in _GENDER else "")
            for p in members
        )
        out += ["", f"# {heading(name)}", "", f"In this group at the boutique: {roll_call}."]
        for product in members:
            out += ["", _product_section(product)]
    return "\n".join(out).rstrip() + "\n"


def render(products: list[dict]) -> dict[str, str]:
    """filename -> markdown, for the three generated documents."""
    by_category: dict[str, list[dict]] = {"fragrance": [], "makeup": [], "skincare": []}
    for product in products:
        category = (product.get("category") or "").lower()
        if category in by_category and product.get("id") and product.get("name"):
            by_category[category].append(product)

    return {
        "fragrance.md": _render(
            "Fragrance at the boutique, by olfactory family",
            "Every fragrance the boutique carries, grouped by olfactory family. Concentrations run "
            "from eau de toilette (lighter) through eau de parfum to parfum and elixir (the most "
            "intense). Prices are in Hong Kong dollars.",
            _group(by_category["fragrance"], lambda p: p.get("family"), "Other"),
            lambda family: f"{family} fragrances",
        ),
        "makeup.md": _render(
            "Makeup at the boutique",
            "Every makeup product the boutique carries, grouped by type. Prices are in Hong Kong dollars.",
            _group(by_category["makeup"], lambda p: (p.get("subcategory") or "").title(), "Other makeup"),
            lambda kind: f"Makeup: {kind}",
        ),
        "skincare.md": _render(
            "Skincare at the boutique",
            "Every skincare product the boutique carries, grouped by type. Prices are in Hong Kong dollars.",
            _group(by_category["skincare"], lambda p: (p.get("subcategory") or "").title(), "Other skincare"),
            lambda kind: f"Skincare: {kind}",
        ),
    }


def write(products: list[dict], out_dir: Path) -> dict[str, int]:
    """Writes the generated documents; returns filename -> product count."""
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for filename, text in render(products).items():
        (out_dir / filename).write_text(text, encoding="utf-8")
        counts[filename] = text.count("\n## ")
    return counts
