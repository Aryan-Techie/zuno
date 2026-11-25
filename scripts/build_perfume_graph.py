"""Build the perfume-mode knowledge graph from the catalog, in Graphify's format.

Graphify's semantic pass reads prose with an LLM. The perfume catalog is
already structured (lines, families, notes, ingredients), so every fact the
graph needs is stated in the data: those edges are EXTRACTED, with no model
in the loop. On top of them it adds one kind of INFERRED edge, "shares notes
with", between fragrances that have two or more notes in common: a real
lead for "if you like X, try Y", but a resolution rather than a stated fact,
which is exactly the line ZUNO's specialist treats differently.

Then Graphify itself clusters the graph, writes the report and draws the
HTML view:

    backend/.venv/bin/python scripts/build_perfume_graph.py
"""
import itertools, json, re, subprocess, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "backend/app/catalogs/perfume.json"
OUT_DIR = ROOT / "backend/app/knowledge/_perfume_build"
GRAPH = ROOT / "backend/app/knowledge/perfume.graph.json"
HTML = ROOT / "frontend/public/graphify/knowledge-perfume.html"


def slug(*parts):
    return re.sub(r"[^a-z0-9]+", "_", "_".join(parts).lower()).strip("_")


def main():
    products = json.loads(CATALOG.read_text())
    nodes, links = {}, []

    def node(nid, label, kind, source="perfume.json"):
        nodes.setdefault(nid, {"id": nid, "label": label, "file_type": kind,
                               "source_file": source, "norm_label": label.lower()})
        return nid

    def link(a, b, relation, confidence="EXTRACTED", score=1.0):
        links.append({"source": a, "target": b, "relation": relation, "confidence": confidence,
                      "confidence_score": score, "weight": score, "source_file": "perfume.json"})

    brand = node("brand_dior", "Dior", "concept")
    for p in products:
        pid = node(slug("product", p["id"]), p["name"], "document")
        link(pid, brand, "made_by")
        cat = node(slug("category", p["category"]), p["category"].title(), "concept")
        link(pid, cat, "in_category")
        if p.get("line"):
            link(pid, node(slug("line", p["line"]), f"{p['line']} line", "concept"), "part_of_line")
        if p.get("family"):
            for fam in re.split(r"\s*,\s*", p["family"]):
                link(pid, node(slug("family", fam), fam, "concept"), "olfactory_family")
        for tier in ("top", "heart", "base"):
            for note in (p.get("notes") or {}).get(tier) or []:
                link(pid, node(slug("note", note), note, "concept"), "has_note")
        for ing in p.get("key_ingredients") or []:
            link(pid, node(slug("ingredient", ing), ing, "concept"), "key_ingredient")

    fragrances = [p for p in products if p["category"] == "fragrance"]
    notes_of = {p["id"]: {n for t in (p.get("notes") or {}).values() for n in (t or [])} for p in fragrances}
    for a, b in itertools.combinations(fragrances, 2):
        shared = notes_of[a["id"]] & notes_of[b["id"]]
        if len(shared) >= 2:
            link(slug("product", a["id"]), slug("product", b["id"]), "shares_notes_with",
                 "INFERRED", round(min(0.95, 0.5 + 0.15 * len(shared)), 2))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = {"directed": False, "multigraph": False,
             "graph": {"schema_version": 1, "hyperedges": []},
             "nodes": list(nodes.values()), "links": links}
    raw = OUT_DIR / "graphify-out" / "graph.json"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(json.dumps(graph))

    subprocess.run(["graphify", "cluster-only", str(OUT_DIR), "--graph", str(raw), "--no-label"], check=True)
    built = json.loads(raw.read_text())

    # Name each community after what dominates it, no model needed.
    by_comm = {}
    for n in built["nodes"]:
        by_comm.setdefault(n.get("community"), []).append(n)
    labels = {}
    for c, members in by_comm.items():
        concepts = Counter(n["label"] for n in members if n["file_type"] == "concept" and n["label"] not in ("Dior", "Fragrance", "Makeup", "Skincare"))
        docs = [n["label"] for n in members if n["file_type"] == "document"]
        labels[c] = (concepts.most_common(1)[0][0] if concepts else (docs[0] if docs else f"Group {c}"))
    for n in built["nodes"]:
        n["community_name"] = labels.get(n.get("community"))
    GRAPH.write_text(json.dumps(built))
    raw.write_text(json.dumps(built))
    labels_file = OUT_DIR / "graphify-out" / ".graphify_labels.json"
    labels_file.write_text(json.dumps({str(k): v for k, v in labels.items()}))
    subprocess.run(["graphify", "export", "html", "--graph", str(raw), "--labels", str(labels_file)], check=True, cwd=OUT_DIR)
    html = next((OUT_DIR / "graphify-out").glob("graph.html"), None) or next(OUT_DIR.rglob("graph.html"))
    HTML.write_text(html.read_text())
    ext = sum(l["confidence"] == "EXTRACTED" for l in built["links"])
    print(f"perfume graph: {len(built['nodes'])} nodes, {len(built['links'])} links "
          f"({ext} extracted, {len(built['links']) - ext} inferred), {len(labels)} communities")


if __name__ == "__main__":
    sys.exit(main())
