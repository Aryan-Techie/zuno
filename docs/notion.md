# ZUNO in Notion, drawn by Graphify

ZUNO mirrors what it knows (the Apple and Dior catalogs) and what it does (leads, calls, objections, meetings) into linked Notion databases under one page called **ZUNO**. [Graphify](https://www.getgraphify.com) reads that workspace and draws it as an interactive knowledge graph, so the graph of the sales operation updates as calls happen.

This document covers what Graphify turns into nodes and links, how the schema follows from that, how to set it up, and what the live sync writes.

---

## 1. What Graphify draws (research, November 2026)

Sources are the Graphify Help Center pages linked inline. Anything not stated there is marked as an inference.

### Nodes

- **A node is one Notion page, or one entry in a Notion database. It is labelled with the page title.** ([Graphify basics](https://docs.getgraphify.com/docs/get-started/graphify-basics))
- Pages that can appear: standard pages, pages nested in other pages, database entries, and pages linked with @, /link to page or a relation. ([Add or remove pages](https://docs.getgraphify.com/docs/keeping-in-sync/add-or-remove-pages))
- **A completely empty page shows up as "Untitled":** "Notion returns no title for a page with no content. Add any block and sync again." ([FAQ](https://docs.getgraphify.com/docs/faq), [Add or remove pages](https://docs.getgraphify.com/docs/keeping-in-sync/add-or-remove-pages))
- A database itself is not listed as a node. Databases show up in Graphify as a **filter** ("Hide whole Notion databases", [Filters](https://docs.getgraphify.com/docs/your-graph/filters)) and as the unit a **Custom Graph** is built from ([Multiple graphs](https://docs.getgraphify.com/docs/your-graph/multiple-graphs)). *Inference: a link pointing at a database draws no line.*

### Links

There are exactly **three link types**, each with its own colour, and they can be shown, hidden or recoloured independently ([Graphify basics](https://docs.getgraphify.com/docs/get-started/graphify-basics), [Filters](https://docs.getgraphify.com/docs/your-graph/filters)):

| Link type | Made in Notion by |
|---|---|
| **mention** | Typing @ and picking a page |
| **relation** | Two database entries connected by a relation property |
| **link to page** | /link to page, or pasting a link to a page |

Rules that matter for the design:

- **Both ends must be shared with Graphify** or no line is drawn. ([Graphify basics](https://docs.getgraphify.com/docs/get-started/graphify-basics), [Something is missing](https://docs.getgraphify.com/docs/fix-a-problem/something-is-missing))
- **A page name typed as plain text is not a link.** "Use @, /link to page, or a database relation." ([How syncing works](https://docs.getgraphify.com/docs/keeping-in-sync/how-syncing-works))
- **Links nested deep in a page can be missed:** "Graphify follows nested blocks to a limited depth. A link buried many levels down inside toggles and columns can be missed." ([Add or remove pages](https://docs.getgraphify.com/docs/keeping-in-sync/add-or-remove-pages))
- **Parent/child nesting and backlinks are not link types.** The docs list only the three above. Child pages come along when their parent is shared, but as nodes, not edges. *Inference from the list being exhaustive: a child page with no mention, relation or link-to-page is an isolated node.*
- A node with no links is an "isolated node", and Graphify has a toggle to hide them. ([Graphify basics](https://docs.getgraphify.com/docs/get-started/graphify-basics), [Your first graph](https://docs.getgraphify.com/docs/get-started/your-first-graph))

### What it reads, and how it syncs

- For each shared page it stores "the title, the properties it needs to draw links and run filters, which database the page belongs to, and when it was last edited. It doesn't store the body of your pages." Access is read-only. ([Connect Notion, web app](https://docs.getgraphify.com/docs/get-started/connect-notion-web), [FAQ](https://docs.getgraphify.com/docs/faq))
- **Status properties are special:** the Appearance panel can "Colour nodes by their Notion status property", and the Filters panel filters by "the values of your Notion status properties". Only the Notion *Status* type, not a select. ([Appearance](https://docs.getgraphify.com/docs/your-graph/appearance), [Filters](https://docs.getgraphify.com/docs/your-graph/filters))
- Sharing: share one top-level page and "Subpages of a connected page are included automatically, and so are entries created in a connected database." ([Add or remove pages](https://docs.getgraphify.com/docs/keeping-in-sync/add-or-remove-pages))
- First sync is a full read (slow on big workspaces because of Notion's rate limits). Later syncs are **smart syncs** of pages edited since the last run; changing a database's structure re-reads all its entries. Syncing never duplicates nodes. A page deleted in Notion disappears at the next sync. ([How syncing works](https://docs.getgraphify.com/docs/keeping-in-sync/how-syncing-works))
- When it syncs: on the web, **automatic sync driven by Notion webhooks is Pro**, otherwise manual. On Desktop: an interval, on launch, or manually (⇧⌘R). ([How syncing works](https://docs.getgraphify.com/docs/keeping-in-sync/how-syncing-works))

### Limits

| Limit | Source |
|---|---|
| **Free web plan syncs up to 100 pages.** Pro removes the limit. Graphify Desktop has no page limit. | [FAQ](https://docs.getgraphify.com/docs/faq), [Add or remove pages](https://docs.getgraphify.com/docs/keeping-in-sync/add-or-remove-pages) |
| On the web, advanced filters, node groups, visual customisation (including size by connections and colour by status), publishing, embedding and automatic sync are **Pro**. All are included in Desktop except publishing and embedding, which are web-only. | [Filters](https://docs.getgraphify.com/docs/your-graph/filters), [Node groups](https://docs.getgraphify.com/docs/your-graph/node-groups), [Appearance](https://docs.getgraphify.com/docs/your-graph/appearance), [Publish a graph](https://docs.getgraphify.com/docs/share-your-graph/publish-a-graph) |
| Nested blocks are followed only to a limited depth. | [Add or remove pages](https://docs.getgraphify.com/docs/keeping-in-sync/add-or-remove-pages) |
| Desktop and web are separate products (one-time license vs Free/Pro account). Desktop is macOS and Windows only. | [Graphify Desktop](https://docs.getgraphify.com/docs/desktop), [FAQ](https://docs.getgraphify.com/docs/faq) |
| A published graph keeps live content but freezes the styling (filters, node groups, colours) at publish time. | [Publish a graph](https://docs.getgraphify.com/docs/share-your-graph/publish-a-graph) |

---

## 2. Schema, and why it looks like this

Design rules, each taken from the facts above:

1. **Every connection worth seeing is a relation property.** Relations are the only link type that lives in properties, which Graphify reads for every page on every sync. All relations are two-way (`dual_property`), so both pages list each other in Notion too. The far side gets a readable name ("Products" on a brand), not Notion's default "Related to Products (Brand)".
2. **Titles are written as node labels:** "Call · Jane Doe (Acme) · 25 Nov 14:02", "Pricing: Too expensive for 40 seats", "Sauvage Eau de Parfum". No uuids in titles.
3. **Every page ZUNO creates has at least one body block**, so none shows up as "Untitled".
4. **Lead stage and objection status are Notion Status properties**, the one type Graphify can colour and filter nodes by. If a workspace rejects a Status schema, setup falls back to a select with the same options and the mirror writes it as a select (the graph just can't colour by it then).
5. **Body links are top-level blocks**, never inside toggles or columns, because of the nesting-depth limit.
6. **Every database has a `ZUNO ID` text property** (`product:dior-sauvage-eau-de-parfum`, `call:<session id>`, `objection:<session>:<topic>:<hash>`). Every write looks the row up by it first, so re-running setup or replaying an event never duplicates a node.
7. **One shared page holds everything.** Share **ZUNO** with Graphify and every database, row and future row is included.

### Databases

| Database | Properties (relations in bold) | Why it is in the graph |
|---|---|---|
| **Brands** | Name, ZUNO ID, Mode, Website, About; far side: **Products** | Two hubs, Apple and Dior. They split the graph into its two catalogs. |
| **Olfactory Families** | Name, ZUNO ID; far side: **Products** | Fragrances that share a family cluster around one node. A catalog family string listing several ("Floral, Vanilla, Sensual") becomes one page per family, so every floral fragrance meets at the same Floral node. |
| **Fragrance Notes** | Name, ZUNO ID, Tiers (top/heart/base); far side: **Top note in**, **Heart note in**, **Base note in** | Notes are what fragrances share, and that sharing is what turns a list into a graph. Three tier relations rather than one, so "bergamot is a top note in 12 fragrances" is answerable in Notion. |
| **Objection Playbook** *(added)* | Name, ZUNO ID, Topic, Guidance; far side: **Objections** | One page per objection type (pricing, trust, product). Each one collects every objection of its type, and when an objection is resolved, ZUNO appends the answer that worked with an **@-mention of the product**. The playbook therefore links objection types to the products and answers that resolved them, and it is the one place in the graph where the *mention* link type carries meaning. |
| **Products** | Name, ZUNO ID, **Brand**, **Families**, **Top notes**, **Heart notes**, **Base notes**, Mode, Category, Line, Gender, Subcategory, Price from, Currency, Sizes, Stock, Product page, Image, Description; far side: **Interested leads**, **Mentioned on calls**, **Objections** | The centre of the graph: the catalog on one side, demand (leads, calls, objections) on the other. "Size by connections" makes the products people actually ask about grow. |
| **Leads** | Name, ZUNO ID, Stage *(status)*, **Products of interest**, Mode, Company, Role, Industry, Email, Phone, Seats, Budget, Timeline, Decision stage, Pain points, Outcome; far side: **Calls**, **Meetings**, **Objections** | Who ZUNO talked to and what they wanted. |
| **Calls** | Name, ZUNO ID, **Lead**, **Products mentioned**, Mode, Outcome, Headline, Next step, Urgency, Duration (s), Started, Session ID; far side: **Objections**, **Meetings**. Body: mode switches and the end-of-call wrap-up. | One node per call, between the lead and the products discussed. |
| **Objections** | Name, ZUNO ID, Status *(status: Open/Resolved)*, **Call**, **Lead**, **Products**, **Playbook**, Topic, Customer said, Answer, Attempts, Mode | Each objection links the person, the call, the product it was about and its playbook page. Coloured by status, open objections stand out. |
| **Meetings** | Name, ZUNO ID, **Lead**, **Call**, When, Rep, Status, Mode | The outcome a sales team counts, attached to the call that produced it. |

Plus two plain pages:

- **ZUNO** (the parent you create). Setup appends one *link to page* block pointing at Start here, so the top page is not an isolated node.
- **Start here** *(added)*, a hub page under ZUNO. It explains the workspace, uses *link to page* blocks for the brand pages and the three playbook pages (drawn as edges, so the hub ties the catalog half and the objection half together), and links each database for human readers.

### The shape of the graph

```
                      Start here ── link to page ──> Apple, Dior (Brands)
                          │                          Pricing / Trust / Product objections (Playbook)
                          ▼
 Brand <── Brand ── Product ── Families ──> Olfactory Family
                      │  ╲── Top/Heart/Base notes ──> Fragrance Note
                      │
   Lead ── Products of interest ──┘
    ▲  ▲                     ▲          ▲
    │  └── Lead ── Call ── Products mentioned
    │               ▲
    └── Lead ── Objection ── Products ──> Product
                   │  ╲── Playbook ──> Playbook page ── @mention ──> Product
                   └── Call
 Meeting ── Lead, Call
```

### Page budget (Graphify Free = 100 pages)

Every row is a page. Today's catalogs seed about 63 pages (2 brands, 7 families, 13 notes, 3 playbook pages, 36 products, plus ZUNO and Start here); a demo call adds about 4 to 6 (lead, call, an objection or two, a meeting). That fits the Free plan for a handful of calls. If the catalogs grow, `--max-pages 100` seeds the subset that fits, fragrances first and keeping `--reserve 20` pages free for live calls, or use Graphify Pro or Desktop, which have no page limit. `--dry-run` prints the count.

---

## 3. Notion API choices

- **`Notion-Version: 2026-03-11`**, pinned in `backend/app/notion/config.py`, overridable with `NOTION_VERSION`. The code uses the data-source model introduced in `2025-09-03` (rows live in a database's data source: `POST /v1/data_sources/{id}/query`, page parent `{"type": "data_source_id"}`, relation schema `{"data_source_id", "type": "dual_property"}`), and none of the fields `2026-03-11` renamed (`archived` → `in_trash`, `after` → `position`, `transcription` → `meeting_notes`), so `2025-09-03` works too. `2022-06-28` does not.
- **Pace:** at most 2.5 requests/second by default (`NOTION_MAX_RPS`), shared by every thread using the client. Notion allows about 3/s per connection, and since 2026 also 180/min per workspace below Business plans, which Graphify's own sync shares.
- **Retries:** 429 (honouring `Retry-After`), 409 `conflict_error`, 5xx and network errors back off exponentially, up to 5 retries. Other 4xx errors raise at once.
- **Status options with groups** (`{"name", "color", "group": "In progress"}`) rely on Notion's 2026 status support. Setup falls back to a select if they are refused.
- `.env` stores **data source ids** (`NOTION_DS_*`), since every row-level call takes one.

---

## 4. Live sync

`backend/app/notion/sync.py::register()` runs at startup through `app/integrations/register_all()`. With `NOTION_TOKEN` and all nine `NOTION_DS_*` set, it subscribes to the integration bus. Otherwise it registers nothing and logs one info line. Handlers run on the bus's background pool and never raise: a Notion failure loses a node, not a turn.

| Bus event | Notion writes |
|---|---|
| `lead_upserted` | Upsert the Lead (Stage from the CRM status). Create the call's page if needed; set its Lead and retitle it with the lead's name. Link products already shown on this call as Products of interest. Link objections raised before the caller was identified. |
| `product_spotlighted` | Find the product, or create it with its brand, families and notes if it was never seeded. Add it to the call's Products mentioned and the lead's Products of interest. Repeat spotlights cost no requests. |
| `objection_logged` | Upsert the Objection (Open/Resolved, attempts, answer) linked to Call, Lead, Playbook, and the product named in the payload, falling back to the product last spotlighted on the call. On first resolution, append the answer to the playbook page with an @-mention of the product. |
| `meeting_booked` | Upsert the Meeting linked to Lead and Call. |
| `mode_changed` | Set the call's (and lead's) Mode, and note the switch in the call's body. |
| `call_ended` | Write Outcome, Headline, Next step, Urgency and Duration. Link every product mentioned to the call and the lead. Append the wrap-up (needs, agreed, owed, risks) to the call's body. |

Concurrency: a per-ZUNO-ID lock plus an in-process ZUNO ID → page id cache, so two pool threads, or a query that has not yet seen a fresh create, cannot write the same call twice. A restart re-finds rows by ZUNO ID.

---

## 5. Setup

### (a) Create the workspace and seed it (one command once you have a token)

1. In Notion, open **notion.so/my-integrations → New connection**, name it "ZUNO", type **Access token**, and copy the `ntn_…` token. It needs read, update and insert content.
2. Create a page called **ZUNO**. In its **••• → Connections** menu, add that connection.
3. From the repo root:

```bash
# Preview: calls nothing, writes nothing
backend/.venv/bin/python scripts/setup_notion.py --dry-run

# Create databases + Start here, seed the catalog, write NOTION_* into backend/.env
NOTION_TOKEN=ntn_xxx backend/.venv/bin/python scripts/setup_notion.py \
  --parent "https://www.notion.so/<workspace>/ZUNO-<32-hex-id>"
```

Then restart the backend. The log line `Notion mirror on: …` confirms the mirror is live. Re-running is safe: it reuses the ids in `backend/.env`, else finds databases by title under the parent, else creates them, and finds rows by ZUNO ID. Useful flags: `--max-pages 100` (fit Graphify Free), `--catalog perfume`, `--no-update` (skip rows that already exist), `--rebuild-start-page`, `--no-env` (print the ids instead of writing the file).

`backend/.env` is rewritten in place: NOTION_* lines the script owns are replaced where they are, everything else (other keys, comments, CRLF line endings, `NOTION_VERSION`/`NOTION_MAX_RPS`) is kept.

### (b) Connect the workspace in Graphify

**Web app (getgraphify.com):** Open Graphify → **Connect Notion** → pick the workspace on Notion's authorisation screen → in the page picker select **ZUNO** → **Allow access**. The first sync starts on its own. Everything under ZUNO, including rows ZUNO adds later, is included. Live calls appear after a sync: automatically on Pro (Notion webhooks), otherwise press sync.

**Graphify Desktop** (no page limit, filters and colours included): Paste a Notion access token into *Connect your workspace*. The same token works, or make a separate read-only one. Then in Notion add that connection to the ZUNO page (••• → Connections). The token alone shows "No pages shared yet". Turn on sync on launch or an interval in Settings, or press ⇧⌘R.

**Suggested view for the demo:** turn on *Size by connections* (popular products grow), hide isolated nodes, *Colour by status* (lead stage, open vs resolved objections), and make a Custom Graph "Sales floor" from Leads, Calls, Objections, Products and Objection Playbook. Node groups by title word work well: "Call ·", "Pricing", "Dior".

---

## 6. Files

| Path | What |
|---|---|
| `backend/app/notion/config.py` | `NotionSettings` (own pydantic-settings class, same env files as `app/config.py`, follows its test blanking) |
| `backend/app/notion/schema.py` | Database specs, property schemas, value encoders, ZUNO ID helpers |
| `backend/app/notion/blocks.py` | Body block builders (paragraph, mention, link to page) |
| `backend/app/notion/client.py` | Rate-limited, retrying httpx client and typed helpers |
| `backend/app/notion/catalog.py` | Catalog loading; brand/family/note derivation; page-budgeted seed plan |
| `backend/app/notion/records.py` | ZUNO records → property values and page bodies |
| `backend/app/notion/provision.py` | Database creation, seed, Start here page, `.env` writer, dry-run plan |
| `backend/app/notion/sync.py` | `register()` and the bus handlers |
| `scripts/setup_notion.py` | The CLI |
| `backend/tests/test_notion_*.py` | Tests against an in-memory fake of the Notion API (`test_notion_fakes.py`) |
