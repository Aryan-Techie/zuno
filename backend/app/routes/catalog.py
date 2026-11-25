"""Public catalog and knowledge-graph endpoints for the console.

Public like the call routes (no dashboard cookie): the live console reads
them during a call, and nothing here is more sensitive than a price list.

    GET /api/catalog?mode=perfume[&category=fragrance][&q=text]
    GET /api/catalog/{id}
    GET /api/catalog/{id}/image
    GET /api/knowledge-graph?mode=apple|perfume
"""
from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from app.catalogs import catalog
from app.knowledge import graph
from app.modes import Mode, default_mode

logger = logging.getLogger("zuno")

router = APIRouter()

# backend/data/ is gitignored: product images are Dior's, fetched on demand
# for the demo console and never committed.
IMAGE_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "images"

# Dior's image CDN sits behind bot rules that 403 a client claiming to be
# Chrome without behaving like one, yet serve an honest non-browser agent.
# Measured: Chrome UA -> 403, plain identifying UA -> 200.
BROWSER_USER_AGENT = "ZUNO-demo/1.0 (+https://github.com/Aryan-Techie/zuno)"
CACHE_CONTROL = "public, max-age=86400"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_FETCH_TIMEOUT_SECONDS = 10.0

# Raster types only. An SVG served from this origin is a script-capable
# document, and nothing in the catalog needs one.
_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/avif": ".avif",
    "image/gif": ".gif",
}
_MEDIA_TYPES = {ext: media for media, ext in _EXTENSIONS.items()}

_fetch_lock = threading.Lock()


@router.get("/api/catalog")
def list_catalog(mode: Mode | None = None, category: str | None = None, q: str | None = None) -> dict:
    mode = mode or default_mode()
    return {"mode": mode, "products": catalog.search(mode, q, category=category)}


@router.get("/api/catalog/{product_id}")
def get_product(product_id: str) -> dict:
    product = catalog.get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"No such product: {product_id}")
    return product


def _cache_stem(product_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", product_id)[:120]


def _cached_image(product_id: str) -> Path | None:
    stem = _cache_stem(product_id)
    for ext in _MEDIA_TYPES:
        path = IMAGE_CACHE_DIR / f"{stem}{ext}"
        if path.is_file():
            return path
    return None


def fetch_image(url: str, referer: str | None = None) -> tuple[bytes, str]:
    """One GET with a browser's headers. Returns (bytes, media type); raises
    ValueError for anything that is not a raster image we are willing to
    serve. Separate so tests replace it instead of the network."""
    headers = {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    response = httpx.get(url, headers=headers, timeout=IMAGE_FETCH_TIMEOUT_SECONDS, follow_redirects=True)
    response.raise_for_status()
    media_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if media_type not in _EXTENSIONS:
        raise ValueError(f"not a raster image: {media_type or 'no content-type'}")
    if len(response.content) > MAX_IMAGE_BYTES:
        raise ValueError("image too large")
    return response.content, media_type


@router.get("/api/catalog/{product_id}/image")
def product_image(product_id: str):
    """The product's image, fetched from its image_url once and then served
    from backend/data/images/. Never hot-linked: the CDN's hotlink rules and
    rate limits are not something a live demo should depend on twice."""
    product = catalog.get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"No such product: {product_id}")

    cached = _cached_image(product_id)
    if cached is not None:
        return FileResponse(
            cached, media_type=_MEDIA_TYPES[cached.suffix], headers={"Cache-Control": CACHE_CONTROL}
        )

    url = product.get("image_url")
    if not url or not str(url).startswith("https://"):
        raise HTTPException(status_code=404, detail=f"No image for product: {product_id}")

    with _fetch_lock:
        # A second request for the same image while the first was fetching
        # finds it cached here rather than fetching it again.
        cached = _cached_image(product_id)
        if cached is not None:
            return FileResponse(
                cached, media_type=_MEDIA_TYPES[cached.suffix], headers={"Cache-Control": CACHE_CONTROL}
            )
        try:
            content, media_type = fetch_image(str(url), referer=product.get("url"))
        except Exception as exc:
            logger.warning("image fetch failed for %s: %s", product_id, exc)
            raise HTTPException(status_code=502, detail="Could not fetch the product image")

        try:
            IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            target = IMAGE_CACHE_DIR / f"{_cache_stem(product_id)}{_EXTENSIONS[media_type]}"
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(content)
            tmp.replace(target)
        except OSError as exc:
            # Serving it uncached is still a working image.
            logger.warning("image cache write failed for %s: %s", product_id, exc)

    return Response(content=content, media_type=media_type, headers={"Cache-Control": CACHE_CONTROL})


@router.get("/api/knowledge-graph")
def knowledge_graph(mode: Mode = "apple") -> dict:
    """The Graphify graph behind a mode's knowledge base, for the console's
    graph view. 404 until that mode's graph has been built."""
    exported = graph.export(mode)
    if exported is None:
        raise HTTPException(status_code=404, detail=f"No knowledge graph for mode: {mode}")
    return {"mode": mode, **exported}
