"""Notion mirror of everything ZUNO knows and does.

The point is the picture, not the storage: Graphify (getgraphify.com) reads a
Notion workspace and draws every page as a node and every mention, relation
property and link-to-page as an edge. So the catalog, the leads, the calls and
the objections ZUNO handles are written into a handful of related databases
under one "ZUNO" page, and Graphify turns that into a live map of the sales
operation. docs/notion.md has the reasoning behind the schema.

    config.py     own settings class, so app/config.py stays untouched
    schema.py     the databases, their properties, value encoders
    blocks.py     page-body builders (paragraphs, mentions, link to page)
    client.py     rate-limited, retrying Notion REST client
    catalog.py    catalog files -> brands, families, notes, products
    records.py    ZUNO payloads -> Notion property values
    provision.py  create the databases, seed the catalog, write backend/.env
    sync.py       bus subscribers that keep the mirror current during calls
"""
