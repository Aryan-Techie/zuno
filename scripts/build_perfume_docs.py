"""Build the boutique's knowledge base from the perfume catalog.

    python scripts/build_perfume_docs.py [--catalog PATH] [--out DIR]

Reads backend/app/catalogs/perfume.json and writes fragrance.md (grouped by
olfactory family), makeup.md and skincare.md into
backend/app/rag/docs_perfume/. boutique_faq.md in that directory is
hand-written and left alone.

Re-run it whenever the catalog changes; a running backend picks the new
documents up on its next restart (or the next reset of the perfume index).
The rendering itself lives in backend/app/rag/perfume_docs.py so the test
suite can exercise exactly what this script writes.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.rag.perfume_docs import write  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", default=str(BACKEND / "app" / "catalogs" / "perfume.json"))
    parser.add_argument("--out", default=str(BACKEND / "app" / "rag" / "docs_perfume"))
    args = parser.parse_args()

    catalog_path = pathlib.Path(args.catalog)
    if not catalog_path.exists():
        print(f"No catalog at {catalog_path} - run the scraper first.", file=sys.stderr)
        return 1
    products = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(products, list):
        print(f"{catalog_path} is not a JSON array of products.", file=sys.stderr)
        return 1

    counts = write(products, pathlib.Path(args.out))
    for filename, count in counts.items():
        print(f"{filename:<14} {count:>4} products")
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
