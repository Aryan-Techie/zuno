"""The two product catalogs, as plain JSON on disk, with per-mode lookup.

    apple.json    - built once from app/rag/docs/pricing.json and the
                    inventory fixtures (USD prices, stock where a stock row
                    exists, null where none does).
    perfume.json  - the Dior beauty catalog, written by a scraper (HK$
                    prices, notes, demo stock).

Both share one schema (CatalogProduct, see the build contract), so the
console, the spotlight and the tools treat them the same way and only the
currency field differs.

Why reload on mtime
-------------------
The perfume file is written by a separate process (first a partial file, then
the full one) while the backend may already be running. A stat per lookup
costs microseconds and means the new file is live on the next question
without a restart. A file caught half-written fails to parse, and then the
last good copy stays in use rather than the catalog going empty mid-call.

Nothing here touches the network: every function is safe on the turn path.
"""
from __future__ import annotations

import json
import logging
import math
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.modes import MODES

logger = logging.getLogger("zuno.catalog")

CATALOG_DIR = Path(__file__).resolve().parent

# Overridable per mode (tests point "perfume" at a fixture).
_PATHS: dict[str, Path] = {mode: CATALOG_DIR / f"{mode}.json" for mode in MODES}

# Single-word aliases that are also ordinary English. A spotlight that fires
# on "it brings me joy" or "I want to capture that feeling" is a card flashing
# up for no reason the caller can see, so these never count as a mention on
# their own. Multi-word aliases containing them ("capture totale") still do.
GENERIC_WORDS = frozenset(
    """
    joy forever capture addict glow poison backstage prestige rouge one lip lips
    oil balm serum cream mask foundation mascara blush powder eau parfum perfume
    fragrance cologne gift set home homme essence elixir pure light fresh bloom
    hydra life dream star
    """.split()
)
_MIN_ALIAS_CHARS = 3

_STOPWORDS = frozenset(
    """
    a an the and or of for to in on at by with is it its this that these those
    i me my we our you your they them he she her his do does have has any some
    what which who how much many can could would like want looking please
    about from one ones
    """.split()
)


def normalise(text: str | None) -> str:
    """Lowercase ASCII-folded words separated by single spaces.

    Apostrophes are dropped rather than spaced, so "J'adore" and "jadore" are
    the same word - aliases are written without punctuation and the caller's
    words have to meet them there.
    """
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"['’`]", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def _tokens(text: str | None) -> list[str]:
    tokens = []
    for token in normalise(text).split():
        # "ipads", "fragrances", "lipsticks" are the singular product.
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        tokens.append(token)
    return tokens


@dataclass
class _Catalog:
    mtime_ns: int | None = None
    products: list[dict] = field(default_factory=list)
    by_id: dict[str, dict] = field(default_factory=dict)
    # normalised alias -> product, longest-first order kept in the regex
    aliases: dict[str, dict] = field(default_factory=dict)
    alias_re: re.Pattern | None = None
    idf: dict[str, float] = field(default_factory=dict)
    search_tokens: dict[str, set[str]] = field(default_factory=dict)


_lock = threading.Lock()
_cache: dict[str, _Catalog] = {}


def set_path(mode: str, path: Path | str) -> None:
    """Point a mode at another file. For tests and one-off tooling."""
    with _lock:
        _PATHS[mode] = Path(path)
        _cache.pop(mode, None)


def path_for(mode: str) -> Path:
    return _PATHS[mode]


def reset() -> None:
    with _lock:
        _cache.clear()


def _valid(entry: Any) -> bool:
    return isinstance(entry, dict) and bool(entry.get("id")) and bool(entry.get("name"))


def _index_text(product: dict) -> str:
    notes = product.get("notes") or {}
    note_words = " ".join(" ".join(v or []) for v in notes.values()) if isinstance(notes, dict) else ""
    return " ".join(
        str(part)
        for part in (
            product.get("name"),
            product.get("line"),
            product.get("brand"),
            product.get("category"),
            product.get("subcategory"),
            product.get("gender"),
            product.get("family"),
            note_words,
            " ".join(product.get("key_ingredients") or []),
            " ".join(product.get("aliases") or []),
            product.get("description"),
        )
        if part
    )


def _build(products: list[dict]) -> _Catalog:
    catalog = _Catalog(products=products)
    catalog.by_id = {p["id"]: p for p in products}

    for product in products:
        spoken = list(product.get("aliases") or []) + [product.get("name") or ""]
        for raw in spoken:
            alias = normalise(raw)
            if len(alias) < _MIN_ALIAS_CHARS:
                continue
            if " " not in alias and alias in GENERIC_WORDS:
                continue
            # First product to claim an alias keeps it. "sauvage" listed on
            # the eau de toilette and the eau de parfum must resolve to one
            # card, and catalog order is the scraper's own ranking.
            catalog.aliases.setdefault(alias, product)

    if catalog.aliases:
        ordered = sorted(catalog.aliases, key=len, reverse=True)
        # An optional plural, because "MacBook Airs" and "two Sauvages" name
        # the product as surely as the singular does.
        catalog.alias_re = re.compile(
            r"\b(?P<alias>" + "|".join(re.escape(a) for a in ordered) + r")(?:e?s)?\b"
        )

    doc_freq: dict[str, int] = {}
    for product in products:
        tokens = set(_tokens(_index_text(product))) - _STOPWORDS
        catalog.search_tokens[product["id"]] = tokens
        for token in tokens:
            doc_freq[token] = doc_freq.get(token, 0) + 1
    total = len(products)
    catalog.idf = {t: math.log((total + 1) / (1 + n)) + 1 for t, n in doc_freq.items()}
    return catalog


def _load(mode: str) -> _Catalog:
    path = _PATHS.get(mode)
    if path is None:
        return _Catalog()
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return _cache.get(mode) or _Catalog()

    cached = _cache.get(mode)
    if cached is not None and cached.mtime_ns == mtime:
        return cached

    with _lock:
        cached = _cache.get(mode)
        if cached is not None and cached.mtime_ns == mtime:
            return cached
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # Most likely the scraper mid-write. Keep serving the last good
            # copy; the next stat will pick the finished file up.
            logger.warning("catalog %s unreadable (%s); keeping previous copy", path.name, exc)
            return cached or _Catalog()
        products = [p for p in raw if _valid(p)] if isinstance(raw, list) else []
        built = _build(products)
        built.mtime_ns = mtime
        _cache[mode] = built
        return built


# --- public API -------------------------------------------------------------


def products(mode: str) -> list[dict]:
    return list(_load(mode).products)


def get(product_id: str, mode: str | None = None) -> dict | None:
    """A product by id, in one mode or (mode=None) in either catalog."""
    for candidate in ([mode] if mode else MODES):
        product = _load(candidate).by_id.get(product_id)
        if product is not None:
            return product
    return None


def mode_of(product_id: str) -> str | None:
    for candidate in MODES:
        if product_id in _load(candidate).by_id:
            return candidate
    return None


def match_alias(text: str | None, mode: str) -> dict | None:
    """The product the caller named, by its spoken alias, or None.

    Word-boundary matching, so "sauvage" does not fire inside another word.
    When several aliases occur, the longest wins: "sauvage elixir" outranks
    "sauvage" in "is sauvage elixir stronger than sauvage", and "ipad pro"
    outranks "ipad". Ties go to the later mention, which is where a sentence
    usually lands.
    """
    catalog = _load(mode)
    if catalog.alias_re is None:
        return None
    normalised = normalise(text)
    if not normalised:
        return None
    best: str | None = None
    best_pos = -1
    for match in catalog.alias_re.finditer(normalised):
        alias = match.group("alias")
        if best is None or len(alias) > len(best) or (len(alias) == len(best) and match.start() > best_pos):
            best, best_pos = alias, match.start()
    return catalog.aliases.get(best) if best else None


def _score(catalog: _Catalog, product: dict, query_tokens: list[str]) -> float:
    if not query_tokens:
        return 0.0
    tokens = catalog.search_tokens.get(product["id"], set())
    unknown = math.log(len(catalog.products) + 1) + 1
    weighted_total = sum(catalog.idf.get(t, unknown) for t in query_tokens)
    matched = sum(catalog.idf.get(t, unknown) for t in query_tokens if t in tokens)
    return matched / weighted_total if weighted_total else 0.0


def search(
    mode: str, q: str | None = None, *, category: str | None = None, limit: int | None = None
) -> list[dict]:
    """Products in a mode, optionally of one category and ranked against `q`.

    Ranking is IDF-weighted word coverage over name, line, family, notes,
    ingredients, aliases and description - enough for "woody", "rose",
    "for men" or "lipstick" without an embedding model on the turn path.
    """
    catalog = _load(mode)
    pool = [
        p for p in catalog.products if not category or (p.get("category") or "").lower() == category.lower()
    ]
    query_tokens = [t for t in _tokens(q) if t not in _STOPWORDS] if q else []
    if not query_tokens:
        return pool[:limit] if limit else pool
    scored = [(p, _score(catalog, p, query_tokens)) for p in pool]
    ranked = [p for p, s in sorted(scored, key=lambda pair: pair[1], reverse=True) if s > 0]
    return ranked[:limit] if limit else ranked


# Same threshold idea as app/inventory/service.py: real phrasings cover most
# of their own words, a product we do not carry covers almost none.
FIND_THRESHOLD = 0.6


def find(query: str | None, mode: str) -> tuple[dict | None, list[dict]]:
    """The product a tool argument names, plus near-misses.

    Order of evidence: an exact id, then a spoken alias inside the query, then
    word coverage. A miss returns (None, closest few) so the caller can offer
    what we do carry instead of inventing something.
    """
    catalog = _load(mode)
    text = (query or "").strip()
    if not text or not catalog.products:
        return None, []

    if text in catalog.by_id:
        return catalog.by_id[text], []

    by_alias = match_alias(text, mode)
    if by_alias is not None:
        return by_alias, []

    query_tokens = [t for t in _tokens(text) if t not in _STOPWORDS]
    scored = sorted(
        ((p, _score(catalog, p, query_tokens)) for p in catalog.products),
        key=lambda pair: pair[1],
        reverse=True,
    )
    best, best_score = scored[0]
    if best_score < FIND_THRESHOLD:
        return None, [p for p, s in scored[:3] if s > 0]
    near = [p for p, s in scored[1:4] if s >= FIND_THRESHOLD and best_score - s <= 0.05]
    return best, near


_ML = re.compile(r"(\d+(?:\.\d+)?)\s*(ml|g|inch|in)\b")


def pick_size(product: dict, text: str | None) -> dict | None:
    """The size a caller named ("the 100 ml", "13 inch"), else the first."""
    sizes = [s for s in (product.get("sizes") or []) if isinstance(s, dict)]
    if not sizes:
        return None
    wanted = _ML.search((text or "").lower())
    if wanted:
        number = wanted.group(1)
        for size in sizes:
            if re.search(rf"\b{re.escape(number)}\b", str(size.get("label", "")).lower()):
                return size
    return sizes[0]


def price_of(size: dict | None, product: dict) -> float | None:
    """A size's price in the catalog's own currency (HKD or USD)."""
    for key in ("price_hkd", "price_usd"):
        if size and size.get(key) is not None:
            return float(size[key])
    for key in ("price_hkd_from", "price_usd_from"):
        if product.get(key) is not None:
            return float(product[key])
    return None


def currency_of(product: dict) -> str:
    if product.get("price_hkd_from") is not None or any(
        "price_hkd" in s for s in (product.get("sizes") or []) if isinstance(s, dict)
    ):
        return "HKD"
    return "USD"


def money(amount: float | None, currency: str) -> str:
    if amount is None:
        return "price on request"
    symbol = "HK$" if currency == "HKD" else "$"
    return f"{symbol}{amount:,.0f}"


def summary(product: dict) -> dict:
    """The facts the model may say about a product, and nothing it may not.

    Handed back by show_product and check_inventory so a recommendation is
    grounded in the catalog row rather than in what the model remembers about
    a famous perfume.
    """
    currency = currency_of(product)
    out: dict[str, Any] = {
        "id": product["id"],
        "name": product.get("name"),
        "brand": product.get("brand"),
        "category": product.get("category"),
        "subcategory": product.get("subcategory"),
        "currency": currency,
        "sizes": [
            {"label": s.get("label"), "price": money(price_of(s, product), currency)}
            for s in (product.get("sizes") or [])
            if isinstance(s, dict)
        ],
    }
    for key in ("gender", "family", "notes", "description"):
        if product.get(key):
            out[key] = product[key]
    if product.get("key_ingredients"):
        out["key_ingredients"] = product["key_ingredients"]
    return out
