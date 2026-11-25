"""Set up the ZUNO Notion workspace that Graphify draws as a knowledge graph.

Creates the databases (Brands, Products, Fragrance Notes, Olfactory Families,
Objection Playbook, Leads, Calls, Objections, Meetings) under one parent page,
seeds the catalog from backend/app/catalogs/{apple,perfume}.json, adds a
"Start here" hub page, and writes the NOTION_* ids into backend/.env so the
backend mirrors live calls into them from then on.

Idempotent: re-running finds what the last run made (by the ids in
backend/.env, then by title under the parent page, then by each row's ZUNO
ID) and only creates what is missing.

    # Before: create an internal integration at notion.so/my-integrations,
    # make a page called ZUNO, and share it with the integration
    # (page ••• menu > Connections).
    backend/.venv/bin/python scripts/setup_notion.py --dry-run
    NOTION_TOKEN=ntn_... backend/.venv/bin/python scripts/setup_notion.py \\
        --parent "https://www.notion.so/ZUNO-<32 hex id>"

Options worth knowing:
    --max-pages 100   seed only what fits Graphify's Free web plan (100 pages),
                      keeping --reserve pages free for live calls
    --catalog perfume seed one catalog only
    --no-update       leave rows that already exist untouched (faster re-run)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.notion.catalog import load_catalogs, build_seed  # noqa: E402
from app.notion.client import NotionClient, NotionError  # noqa: E402
from app.notion.config import DATA_SOURCE_ENV, load_notion_settings  # noqa: E402
from app.notion.provision import (  # noqa: E402
    Provisioner,
    SetupResult,
    describe_plan,
    parse_page_id,
    write_env,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--token", help="Notion integration token (default: NOTION_TOKEN)")
    parser.add_argument("--parent", help="parent page id or URL (default: NOTION_PARENT_PAGE_ID)")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, call nothing, write nothing")
    parser.add_argument("--catalog", choices=("all", "apple", "perfume"), default="all")
    parser.add_argument("--max-products", type=int, help="at most this many products per catalog")
    parser.add_argument("--max-pages", type=int, help="page budget for the whole workspace (Graphify Free: 100)")
    parser.add_argument("--reserve", type=int, default=20, help="pages kept free for live calls under --max-pages")
    parser.add_argument("--no-seed", action="store_true", help="create the databases and hub page only")
    parser.add_argument("--no-update", action="store_true", help="skip catalog rows that already exist")
    parser.add_argument("--rebuild-start-page", action="store_true", help="rewrite the Start here page body")
    parser.add_argument("--env-file", type=Path, default=BACKEND_DIR / ".env", help="env file to write ids into")
    parser.add_argument("--no-env", action="store_true", help="print the ids instead of writing the env file")
    return parser.parse_args()


def main() -> int:
    args = _args()
    settings = load_notion_settings()
    token = (args.token or os.environ.get("NOTION_TOKEN") or settings.notion_token).strip()
    parent_raw = args.parent or os.environ.get("NOTION_PARENT_PAGE_ID") or settings.notion_parent_page_id
    known = {key: value for key, value in settings.data_source_ids().items() if value}

    modes = ("apple", "perfume") if args.catalog == "all" else (args.catalog,)
    catalogs = load_catalogs()
    for mode in modes:
        if mode not in catalogs:
            print(f"note: no {mode} catalog found in backend/app/catalogs, skipping it")
    plan = build_seed(
        catalogs,
        modes=modes,
        max_products=args.max_products,
        max_pages=args.max_pages,
        reserve_pages=args.reserve if args.max_pages is not None else 0,
    )

    if args.dry_run:
        parent_note = "not set"
        if parent_raw:
            try:
                parent_note = parse_page_id(parent_raw)
            except ValueError as exc:
                parent_note = f"invalid ({exc})"
        print("DRY RUN: nothing is sent to Notion and no file is written.\n")
        print(f"Parent page: {parent_note}")
        print(f"Token: {'set' if token else 'not set'}   Notion-Version: {settings.notion_version}\n")
        for line in describe_plan(plan, seed=not args.no_seed, max_rps=settings.notion_max_rps, known=known):
            print(line)
        print(f"\nWould write to {args.env_file}: NOTION_TOKEN, NOTION_PARENT_PAGE_ID, NOTION_START_PAGE_ID, "
              + ", ".join(DATA_SOURCE_ENV.values()))
        return 0

    if not token:
        print("error: no Notion token. Pass --token or set NOTION_TOKEN.", file=sys.stderr)
        return 2
    if not parent_raw:
        print("error: no parent page. Pass --parent <page URL or id> or set NOTION_PARENT_PAGE_ID.", file=sys.stderr)
        return 2
    try:
        parent = parse_page_id(parent_raw)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    client = NotionClient(token, version=settings.notion_version, max_rps=settings.notion_max_rps)
    provisioner = Provisioner(client, parent)
    started = time.monotonic()
    try:
        try:
            client.retrieve_page(parent)
        except NotionError as exc:
            if exc.status in (401, 403, 404):
                print(
                    "error: the integration cannot open that page. Check the token, then share the page "
                    "with the integration (page ••• menu > Connections).",
                    file=sys.stderr,
                )
                return 1
            raise

        print("Databases:")
        refs = provisioner.ensure_databases(known)
        result = SetupResult(refs)

        if not args.no_seed:
            print(f"Seeding {plan.page_count()} catalog rows (about {plan.page_count() / settings.notion_max_rps / 60:.1f} min)...")
            result.seeded = provisioner.seed(refs, plan, update_existing=not args.no_update)
            for db, counts in result.seeded.items():
                print(f"  {db:<10} " + ", ".join(f"{n} {k}" for k, n in counts.items() if n))

        print("Hub page:")
        result.start_page_id = provisioner.ensure_start_page(
            refs,
            provisioner.hub_pages(refs),
            known_id=settings.notion_start_page_id or None,
            rebuild=args.rebuild_start_page,
        )
    except NotionError as exc:
        print(f"error: Notion refused a request: {exc}", file=sys.stderr)
        print("Re-running is safe; it picks up where this stopped.", file=sys.stderr)
        return 1
    finally:
        client.close()

    values = result.env_values(token, parent)
    if args.no_env:
        print("\nAdd these to backend/.env:")
        for key, value in values.items():
            print(f"{key}={'<your token>' if key == 'NOTION_TOKEN' else value}")
    else:
        write_env(args.env_file, values)
        print(f"\nWrote {len(values)} NOTION_* settings to {args.env_file} (token included, not shown).")
    print(f"Done in {time.monotonic() - started:.0f}s. Restart the backend to start mirroring calls.")
    print("Next: getgraphify.com > Connect Notion > pick this workspace > allow access to the ZUNO page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
