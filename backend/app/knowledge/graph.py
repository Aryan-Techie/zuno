"""Graphify product knowledge graphs, read at answer time.

Graphify turns the knowledge-base documents into a node-link graph
(app/knowledge/{mode}.graph.json): concepts as nodes, and edges between them
that are either EXTRACTED (stated in a document) or INFERRED (a connection
Graphify resolved across documents that no single sentence states). The
retriever finds paragraphs that share words with a question; the graph adds
what those paragraphs are *connected to* - the FAQ answer about trade-in and
the Enterprise tier feature it hangs off, which keyword search returns as two
unrelated chunks, if it returns the second at all.

The specialist (app/specialists/solutions.py) gets these as an extra reference
chunk, with the confidence label on every line. That label is the point: an
EXTRACTED edge is something our documents say and can be relied on; an
INFERRED one is a lead worth checking, and the specialist is told to put it in
open_questions rather than promise it.

Zero dependencies, no network: one JSON load per file change, then dict
lookups. A missing graph (perfume.graph.json is added later) is simply no
facts, never an error.
"""
from __future__ import annotations

import json
import logging
import math
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("zuno.knowledge")

GRAPH_DIR = Path(__file__).resolve().parent

_WORD = re.compile(r"[a-z0-9]+")

# Words that say nothing about which concept is meant. Kept small on purpose:
# the IDF weighting below already discounts words most labels share ("apple",
# "faq"), so this only needs to catch the grammar.
STOPWORDS = frozenset(
    """
    a an the and or of for to in on at by with is are was were be been it its this
    that these those i me my we our us you your they them their he she his her do
    does did have has had can could would should will shall may might must what
    which who whom how when where why if then than so not no yes any some all
    about into from up down out over under again more most such only own same too
    very just also there here get got want need like
    """.split()
)

# How many seed nodes a question may light up. Past a handful the 1-hop
# neighbourhood is most of a small graph, and the facts stop being about the
# question.
MAX_SEEDS = 5
# A seed must match at least this share of the best seed's score, so one
# strong match is not padded out with nodes that merely share a common word.
SEED_RELATIVE_FLOOR = 0.35
# Document nodes ("Apple for Business FAQ") are hubs: every concept in the file
# hangs off them, so as a seed they spend the whole fact budget on "the FAQ
# references X" lines. Halved, a document only seeds when nothing more
# specific matched - measured on "does Apple Business Manager work with Jamf",
# where at full weight the FAQ hub pushed the Jamf node out of the seeds.
DOCUMENT_SEED_WEIGHT = 0.5


@dataclass
class _Graph:
    mtime_ns: int | None = None
    nodes: list[dict] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)
    by_id: dict[str, dict] = field(default_factory=dict)
    label_tokens: dict[str, set[str]] = field(default_factory=dict)
    idf: dict[str, float] = field(default_factory=dict)
    adjacency: dict[str, list[dict]] = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


_lock = threading.Lock()
_cache: dict[str, _Graph] = {}
# Overridable (tests point a mode at a fixture or a missing file).
_PATHS: dict[str, Path] = {}


def path_for(mode: str) -> Path:
    return _PATHS.get(mode) or GRAPH_DIR / f"{mode}.graph.json"


def set_path(mode: str, path: Path | str) -> None:
    with _lock:
        _PATHS[mode] = Path(path)
        _cache.pop(mode, None)


def reset() -> None:
    with _lock:
        _cache.clear()
        _PATHS.clear()


def _tokens(text: str | None) -> set[str]:
    out = set()
    for token in _WORD.findall((text or "").lower()):
        if token in STOPWORDS or len(token) < 2:
            continue
        # "trade-ins" and "tiers" should meet "trade-in" and "tier".
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        out.add(token)
    return out


def _is_code(node: dict | None) -> bool:
    return bool(node) and node.get("file_type") == "code"


def _build(raw: dict) -> _Graph:
    nodes = [n for n in raw.get("nodes") or [] if isinstance(n, dict) and n.get("id")]
    links = [l for l in raw.get("links") or raw.get("edges") or [] if isinstance(l, dict)]
    graph = _Graph(nodes=nodes, links=links, raw=raw)
    graph.by_id = {n["id"]: n for n in nodes}

    doc_freq: dict[str, int] = {}
    for node in nodes:
        if _is_code(node):
            continue
        tokens = _tokens(node.get("label") or node["id"])
        graph.label_tokens[node["id"]] = tokens
        for token in tokens:
            doc_freq[token] = doc_freq.get(token, 0) + 1
    total = max(1, len(graph.label_tokens))
    graph.idf = {t: math.log((total + 1) / (1 + n)) + 1 for t, n in doc_freq.items()}

    for link in links:
        for end in ("source", "target"):
            graph.adjacency.setdefault(str(link.get(end)), []).append(link)
    return graph


def _load(mode: str) -> _Graph | None:
    path = path_for(mode)
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return None
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
            logger.warning("knowledge graph %s unreadable (%s)", path.name, exc)
            return cached
        graph = _build(raw if isinstance(raw, dict) else {})
        graph.mtime_ns = mtime
        _cache[mode] = graph
        return graph


def exists(mode: str) -> bool:
    return _load(mode) is not None


def _label(graph: _Graph, node_id: str) -> str:
    node = graph.by_id.get(node_id)
    return (node or {}).get("label") or node_id


def _seeds(graph: _Graph, question: str) -> list[tuple[str, float]]:
    asked = _tokens(question)
    if not asked:
        return []
    scored = []
    for node_id, tokens in graph.label_tokens.items():
        overlap = asked & tokens
        if overlap:
            score = sum(graph.idf.get(t, 1.0) for t in overlap)
            if (graph.by_id.get(node_id) or {}).get("file_type") == "document":
                score *= DOCUMENT_SEED_WEIGHT
            scored.append((node_id, score))
    if not scored:
        return []
    scored.sort(key=lambda pair: pair[1], reverse=True)
    floor = scored[0][1] * SEED_RELATIVE_FLOOR
    return [pair for pair in scored if pair[1] >= floor][:MAX_SEEDS]


def facts_for(question: str, mode: str, limit: int = 10) -> list[str]:
    """Graph edges around the concepts a question names, as one line each:

        A --relation--> B [EXTRACTED|INFERRED, source_file]

    Seeds are nodes whose label shares (IDF-weighted) words with the
    question, skipping code nodes and stopwords; each seed contributes its
    1-hop edges. EXTRACTED lines come first, because those are the ones that
    may be relied on; within each, edges of the better-matching seed lead.
    """
    graph = _load(mode)
    if graph is None or limit <= 0:
        return []

    seen: set[tuple[str, str, str]] = set()
    ranked: list[tuple[int, float, float, str]] = []
    for node_id, seed_score in _seeds(graph, question):
        for link in graph.adjacency.get(node_id, []):
            source, target = str(link.get("source")), str(link.get("target"))
            if _is_code(graph.by_id.get(source)) or _is_code(graph.by_id.get(target)):
                continue
            relation = link.get("relation") or "related_to"
            key = (source, relation, target)
            if key in seen:
                continue
            seen.add(key)
            confidence = (link.get("confidence") or "INFERRED").upper()
            line = (
                f"{_label(graph, source)} --{relation}--> {_label(graph, target)} "
                f"[{confidence}, {link.get('source_file') or 'unknown source'}]"
            )
            ranked.append(
                (
                    0 if confidence == "EXTRACTED" else 1,
                    -seed_score,
                    -float(link.get("confidence_score") or 0.0),
                    line,
                )
            )
    ranked.sort(key=lambda row: row[:3])
    return [row[3] for row in ranked[:limit]]


def stats(mode: str) -> dict | None:
    """Counts for the console's knowledge-graph view, or None when this mode
    has no graph yet."""
    graph = _load(mode)
    if graph is None:
        return None
    confidences = [(l.get("confidence") or "").upper() for l in graph.links]
    communities = {n.get("community") for n in graph.nodes if n.get("community") is not None}
    return {
        "nodes": len(graph.nodes),
        "links": len(graph.links),
        "extracted": confidences.count("EXTRACTED"),
        "inferred": confidences.count("INFERRED"),
        "communities": len(communities),
    }


def export(mode: str) -> dict | None:
    """Nodes and links as Graphify wrote them, plus stats - the
    /api/knowledge-graph payload, minus the mode."""
    graph = _load(mode)
    if graph is None:
        return None
    return {"nodes": graph.nodes, "links": graph.links, "stats": stats(mode)}
