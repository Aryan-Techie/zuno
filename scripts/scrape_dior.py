"""Scrape the Dior beauty catalog (Hong Kong site, HK$ prices) for ZUNO's perfume mode.

Writes backend/app/catalogs/perfume.json: a JSON array of CatalogProduct
objects (schema in the perfume-mode contract). Fragrance comes first, about 40
of them, then about 20 makeup and 20 skincare products. Every product, price,
size, note and image URL comes from www.dior.com/en_hk/beauty; nothing is
invented. When the site does not state something (an olfactory family, key
ingredients) the field is left empty or null rather than guessed.

Why a real browser: dior.com sits behind Akamai bot protection, which answers
plain HTTP clients (curl, httpx) with a 403 "Page unavailable". A real
Chromium-family browser driven by Playwright gets the normal pages. We drive an
already installed Brave (or Helium) through `executable_path` with a fresh,
throwaway profile in the work dir, never a personal profile, and never download
a bundled Chromium. Headless works once the "HeadlessChrome" token is removed
from the User-Agent; pass --headful if Akamai ever starts refusing that.

Product images are only downloaded into the work dir to compute `color_hex`
(the tint for the 3D bottle in the console); the catalog stores the Dior CDN
URL. The image CDN, unlike the HTML pages, serves plain clients that send a
non-browser User-Agent (it 403s a spoofed Chrome UA coming from a non-browser
TLS stack), so images are fetched with httpx's default UA.

Dependencies (install into a throwaway venv, NOT backend/requirements.txt):

    pip install playwright pillow httpx

No `playwright install` is needed: the script uses the system browser.

How to run (from the repo root):

    python scripts/scrape_dior.py \
        --work-dir /tmp/dior-scrape \
        --out backend/app/catalogs/perfume.json

Useful flags:
    --browser PATH     Chromium-family browser binary (default: Brave, then Helium)
    --headful          show the browser window (fallback if headless gets blocked)
    --use-cache        reuse product pages already saved under --work-dir/raw
                       (re-run the parsing/colour/alias steps without hitting the site)
    --offline          with --use-cache: build only from saved pages, never open the browser
    --discover-only    list what the category pages offer, then stop
    --quota F,M,S      products per category (default 40,20,20)

Politeness: one page at a time with a pause of --delay seconds (default 2.0)
between page loads, so well under one request per second for documents.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

BASE = "https://www.dior.com"
SITE = f"{BASE}/en_hk/beauty"

DEFAULT_BROWSERS = [
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Helium.app/Contents/MacOS/Helium",
]

# A current desktop Chrome UA. Headless Chromium advertises "HeadlessChrome",
# which is exactly what Akamai keys on, so the context overrides it.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)

# Category listing pages to discover products from. The category a product
# lands in is decided later from the product page's own breadcrumb, so a tile
# that shows up on the "wrong" listing does not matter.
LISTING_PAGES: dict[str, list[str]] = {
    "fragrance": [
        "/fragrance/womens-fragrance",
        "/fragrance/mens-fragrance",
        "/fragrance/womens-fragrance/miss-dior",
        "/fragrance/womens-fragrance/j%E2%80%99adore",
        "/fragrance/womens-fragrance/poison",
        "/fragrance/mens-fragrance/sauvage",
        "/fragrance/mens-fragrance/dior-homme",
        "/fragrance/mens-fragrance/fahrenheit",
        "/fragrance/mens-fragrance/eau-sauvage",
    ],
    "makeup": [
        "/makeup/lips/lipsticks",
        "/makeup/lips/lip-balm",
        "/makeup/lips/gloss-plumper",
        "/makeup/lips/liquid-lipstick",
        "/makeup/face/foundation",
        "/makeup/face/cushion-foundation",
        "/makeup/face/concealers",
        "/makeup/face/powders",
        "/makeup/face/blush",
        "/makeup/face/highlighter---luminizer",
        "/makeup/face/primers",
        "/makeup/eyes/mascaras",
        "/makeup/eyes/eyeshadows",
        "/makeup/eyes/liners",
        "/makeup/eyes/eyebrows",
        "/makeup/nails-3",
    ],
    "skincare": [
        "/skincare/the-products/serums",
        "/skincare/the-products/creams",
        "/skincare/the-products/eye-contour-care",
        "/skincare/the-products/cleansers",
        "/skincare/the-products/mists-toners",
        "/skincare/your-needs/sun-care-uv-protection",
        "/skincare/the-products/mens-care",
    ],
}

# Which products to take, in order, per category. Names are matched against
# the listing tiles (case, accent and apostrophe-insensitive). The order puts
# the big lines first; anything named here that the site no longer lists is
# simply skipped, and a category that comes up short is topped up from the
# rest of its listings (minus refills, cases, sets and accessories).
PRIORITY: dict[str, list[str]] = {
    "fragrance": [
        # Women: the house pillars.
        "J'adore Eau de Parfum", "J'adore Eau de Toilette", "J'adore Intense",
        "J'adore l'Or", "J'adore Parfum d'eau",
        "Miss Dior Eau de Parfum", "Miss Dior Blooming Bouquet", "Miss Dior Parfum",
        "Miss Dior Essence", "Miss Dior Rose N'Roses",
        "Hypnotic Poison", "Poison Girl", "Pure Poison", "Poison",
        "Dior Addict Eau de Parfum", "JOY by Dior", "JOY by Dior",  # EDP and Intense
        # Men.
        "Sauvage Eau de Toilette", "Sauvage Eau de Parfum", "Sauvage Parfum",
        "Sauvage Elixir", "Sauvage Eau Forte", "Sauvage Extrait",
        "Dior Homme Eau de Toilette", "Dior Homme Parfum", "Dior Homme Sport",
        "Dior Homme Cologne", "Fahrenheit Eau de Toilette",
        # La Collection Privée.
        "Gris Dior", "Bois d'Argent", "Oud Ispahan", "Ambre Nuit",
        "Jasmin des Anges", "Dior Paradise", "Cuir Saddle", "Rose Star",
        "Bois Talisman", "Dioriviera", "Rouge Trafalgar Esprit de Parfum",
        # Dioriginals.
        "Diorissimo", "Dune",
    ],
    "makeup": [
        # Lips.
        "Rouge Dior", "Dior Addict", "Dior Addict Lip Glow", "Dior Addict Lip Maximizer",
        "Dior Addict Lip Glow Oil", "Rouge Dior On Stage",
        # Face.
        "Dior Forever Skin Glow", "Dior Forever Skin Wear", "Dior Forever Cushion",
        "Dior Forever Skin Correct", "Dior Forever Natural Velvet", "Dior Backstage Rosy Glow",
        "Rouge Blush", "Dior Forever Glow Maximizer", "Dior Forever Skin Veil",
        # Eyes and nails.
        "Diorshow Iconic Overcurl", "Diorshow Overvolume", "Diorshow 5 Couleurs",
        "Diorshow Stylo", "Dior Vernis",
        # Spares, used only if one of the above disappears from the site.
        "Rouge Premier", "Dior Addict Lip Tint", "Rouge Dior Balm", "Diorshow Mono Couleur",
    ],
    "skincare": [
        "Dior Capture Le Sérum", "Dior Capture Hyalushot Advanced", "Dior Capture PDRN-Shot",
        "Capture Totale Retishot", "Dior Capture Rich Creme", "Dior Capture Day Creme",
        "Dior Capture Pro-Collagen Shot",
        "Dior Prestige La Micro-Huile de Rose Activated Serum", "Dior Prestige Le Nectar Premier",
        "Dior Prestige La Crème Texture Essentielle", "Dior Prestige La Lotion Essence de Rose",
        "Dior Prestige Le Micro-Sérum de Rose Yeux Activated",
        "L'Or de Vie Le Sérum", "Dior Snow Essence of Light Serum", "Dior Snow UV Shield",
        "One Essential Skin Boosting Super Serum", "Dior Hydra Life Fresh Sorbet Creme",
        "Le Baume", "La Mousse OFF/ON Foaming Cleanser",
        "Dior Homme Dermo System Smoothing Firming Care",
        # Spares.
        "Hydrating Invisible UV Fluid SPF 50+ PA++++", "Dior Capture Night Creme",
        "Dior Capture Eye Creme",
    ],
}

# Tiles never worth selling as a standalone product in a voice demo.
EXCLUDE = re.compile(
    r"\b(refill|recharge|case|brush|mirror|pouch|set|coffret|ritual|calendar|"
    r"candle|perfumer.s palette|mini miss|roller|roller-pearl|hair|body|shower|"
    r"hand cream|soap|discovery|sample|gift|travel|engrav|duo|trio|deodorant|"
    r"after-?shave|aftershave|shaving|shampoo|adorables)\b|"
    r"limited edition|customizable",
    re.I,
)

# Single spoken words that occur in ordinary conversation; never usable as an
# alias on their own (the contract bans the first three explicitly).
GENERIC_ALIASES = {
    "dior", "parfum", "rouge", "perfume", "fragrance", "lipstick", "serum",
    "cream", "poison", "joy", "dune", "higher", "capture", "addict", "forever",
    "glow", "snow", "essence", "intense", "elixir", "sport", "cologne",
    "extrait", "jules", "mascara", "foundation", "blush", "cushion", "balm",
    "le baume", "eau fraiche", "rose star", "one essential", "prestige",
}

# A bare line name ("sauvage", "jadore") is said far more often than a full
# product name, so each one points at a single flagship product.
FLAGSHIP_ALIASES = {
    "sauvage": "Sauvage Eau de Parfum",
    "dior sauvage": "Sauvage Eau de Parfum",
    "jadore": "J'adore Eau de Parfum",
    "miss dior": "Miss Dior Eau de Parfum",
    "dior homme": "Dior Homme Eau de Toilette",
    "dior poison": "Poison",
    "dior joy": "JOY by Dior Eau de Parfum",
    "dior addict perfume": "Dior Addict Eau de Parfum",
    "dior lipstick": "Rouge Dior",
    "rouge dior lipstick": "Rouge Dior",
    "dior capture serum": "Dior Capture Le Sérum",
}

# Lines inferred from the product name; the site's own "collection" field is
# an internal merchandising code ("Core Capture", "DA MU Lip Color").
LINE_PREFIXES = [
    ("sauvage", "Sauvage"), ("eau sauvage", "Eau Sauvage"), ("j'adore", "J'adore"),
    ("l'or de j'adore", "J'adore"), ("miss dior", "Miss Dior"), ("dior homme", "Dior Homme"),
    ("hypnotic poison", "Poison"), ("poison", "Poison"), ("pure poison", "Poison"),
    ("joy", "JOY by Dior"), ("dior addict eau", "Dior Addict"), ("fahrenheit", "Fahrenheit"),
    ("rouge dior", "Rouge Dior"), ("rouge premier", "Rouge Premier"), ("rouge blush", "Rouge Blush"),
    ("dior addict", "Dior Addict"), ("dior forever", "Dior Forever"), ("diorshow", "Diorshow"),
    ("dior backstage", "Dior Backstage"), ("dior vernis", "Dior Vernis"),
    ("dior capture", "Dior Capture"), ("capture totale", "Dior Capture"),
    ("dior prestige", "Dior Prestige"), ("l'or de vie", "L'Or de Vie"),
    ("dior snow", "Dior Snow"), ("diorsnow", "Dior Snow"), ("one essential", "One Essential"),
    ("dior hydra life", "Dior Hydra Life"), ("hydra life", "Dior Hydra Life"),
    ("le baume", "Le Baume"), ("la mousse", "Dior Cleansers OFF/ON"),
]

# Fragrance concentrations, longest first so "eau de parfum" wins over "parfum".
CONCENTRATIONS = [
    ("eau de parfum intense", "eau de parfum intense"), ("esprit de parfum", "esprit de parfum"),
    ("extrait de parfum", "extrait de parfum"), ("essence de parfum", "essence de parfum"),
    ("eau de parfum", "eau de parfum"),
    ("eau de toilette", "eau de toilette"), ("eau de cologne", "eau de cologne"),
    ("parfum d'eau", "parfum d'eau"), ("cologne", "cologne"), ("elixir", "elixir"),
    ("extrait", "extrait de parfum"), ("parfum", "parfum"), ("eau forte", "eau de parfum"),
]

# Carousel headings that introduce a product's star ingredients/technology.
INGREDIENT_SECTIONS = {
    "innovation", "ingredients", "key ingredients", "formula", "the formula",
    "composition", "science", "dior science", "the science", "formulation",
    "key actives", "active ingredients", "ingredient", "the ingredients", "actives",
}

# Fragrance notes are graph nodes (Notion and the Graphify knowledge graph
# link perfumes through shared notes), so every note is one short ingredient
# with one canonical name: origins, varieties and adjectives go ("Calabrian
# bergamot", "bergamot essence" -> "Bergamot"; "Damascus rose essence" ->
# "Rose"). Patterns run against accent-folded lowercase text; where two
# overlap, the longer match wins ("orange blossom" over "orange").
NOTE_VOCAB: list[tuple[str, str]] = [
    # Citrus and aromatics.
    ("Bergamot", r"bergamot|bergamote"), ("Mandarin", r"mandarin"),
    ("Blood Orange", r"blood oranges?"), ("Orange Blossom", r"orange blossom|orange flower|fleur d.oranger"),
    ("Neroli", r"neroli"), ("Orange", r"\boranges?\b"), ("Lemon", r"\blemons?\b"),
    ("Grapefruit", r"grapefruit|pamplemousse"), ("Yuzu", r"\byuzu\b"), ("Lime", r"\blimes?\b"),
    ("Citrus", r"\bcitrus|hesperid"), ("Lavender", r"lavender|lavande"), ("Geranium", r"geranium"),
    ("Sage", r"\bsage\b"), ("Rosemary", r"rosemary"), ("Mint", r"\bmint\b"), ("Basil", r"\bbasil\b"),
    ("Coriander", r"coriander"), ("Juniper", r"juniper"),
    # Spices.
    ("Pink Pepper", r"pink pepper"), ("Pepper", r"\bpepper(?!y)"), ("Elemi", r"\belemi\b"),
    ("Cardamom", r"cardamom"), ("Cinnamon", r"cinnamon"), ("Nutmeg", r"nutmeg"), ("Clove", r"\bcloves?\b"),
    ("Saffron", r"saffron"), ("Ginger", r"\bginger\b"), ("Cumin", r"\bcumin\b"),
    ("Spices", r"\bspices?\b|\bspicy\b"),
    # Flowers.
    ("Tuberose", r"tuberose"), ("Rose", r"\broses?\b(?![- ]?wood)"), ("Jasmine", r"\bjasmin(e)?\b|\bsambac\b|grandiflorum"),
    ("Ylang-Ylang", r"ylang"), ("Iris", r"\biris\b|\borris\b"), ("Violet Leaf", r"violet lea(f|ves)"),
    ("Violet", r"\bviolets?\b"), ("Peony", r"\bpeon(y|ies)\b"), ("Magnolia", r"magnolia"),
    ("Lily of the Valley", r"lily[- ]of[- ]the[- ]valley|muguet"), ("Lily", r"\blil(y|ies)\b"),
    ("Freesia", r"freesia"), ("Mimosa", r"mimosa"), ("Osmanthus", r"osmanthus"), ("Gardenia", r"gardenia"),
    ("Heliotrope", r"heliotrope"), ("Carnation", r"carnation"), ("Honeysuckle", r"honeysuckle"),
    ("Lilac", r"\blilac"), ("Hyacinth", r"hyacinth"), ("Narcissus", r"narcissus"), ("Orchid", r"orchid"),
    ("Elderflower", r"elder ?flower"), ("Lotus", r"\blotus\b"),
    # Fruits.
    ("Blackberry", r"blackberr(y|ies)"), ("Blackcurrant", r"blackcurrant|cassis"), ("Raspberry", r"raspberr"),
    ("Strawberry", r"strawberr"), ("Cherry", r"\bcherr(y|ies)\b"), ("Apricot", r"apricot"), ("Peach", r"\bpeach"),
    ("Pear", r"\bpears?\b"), ("Apple", r"\bapples?\b"), ("Plum", r"\bplums?\b"), ("Fig", r"\bfigs?\b"),
    ("Pineapple", r"pineapple"), ("Coconut", r"coconut"), ("Lychee", r"lychee|litchi"), ("Pomegranate", r"pomegranate"),
    # Gourmand and balsamic.
    ("Vanilla", r"vanill"), ("Tonka Bean", r"tonka"), ("Almond", r"almond|orgeat"), ("Honey", r"\bhoney"),
    ("Caramel", r"caramel"), ("Praline", r"praline"), ("Cocoa", r"cocoa|cacao|chocolate"), ("Coffee", r"coffee"),
    ("Licorice", r"licorice|liquorice"), ("Benzoin", r"benzoin"), ("Opoponax", r"opopona"),
    ("Labdanum", r"labdanum"), ("Myrrh", r"myrrh"), ("Incense", r"incense|olibanum"),
    ("Ambergris", r"ambergris"), ("Ambroxan", r"ambroxan"), ("Amber", r"\bamber(y)?\b|\bambre\b"),
    # Woods, moss and musk.
    ("Sandalwood", r"sandal"), ("Cedarwood", r"\bcedar"), ("Vetiver", r"vetiver"), ("Patchouli", r"patchouli"),
    ("Oud", r"\boud\b|agarwood"), ("Oakmoss", r"oak ?moss|mousse de chene"), ("Oak", r"\boak\b"),
    ("Rosewood", r"rose ?wood"), ("Guaiac Wood", r"guaiac"), ("Birch", r"\bbirch"), ("Cypress", r"cypress"),
    ("Pine", r"\bpine\b"), ("Papyrus", r"papyrus"), ("Cashmere Wood", r"cashmere ?wood|cashmeran"),
    ("Iso E Super", r"\biso e\b"), ("Moss", r"\bmoss\b"), ("Woods", r"\bwoods?\b|\bwoody\b"),
    ("Musk", r"\bmus(k|c)"), ("Leather", r"leather|\bsuede\b|\bcuir\b"), ("Tobacco", r"tobacco"),
    ("Aldehydes", r"aldehyd"), ("Galbanum", r"galbanum"),
]

# A generic note is dropped when the same text already names a specific
# one ("noble wood essences: patchouli, vetiver..." is not also "Woods").
GENERIC_NOTES = {
    "Woods": {"Sandalwood", "Cedarwood", "Vetiver", "Patchouli", "Oud", "Oak", "Rosewood", "Guaiac Wood",
              "Birch", "Cypress", "Pine", "Cashmere Wood", "Papyrus"},
    "Citrus": {"Bergamot", "Mandarin", "Blood Orange", "Orange", "Lemon", "Grapefruit", "Yuzu", "Lime", "Neroli"},
    "Spices": {"Pepper", "Pink Pepper", "Cardamom", "Cinnamon", "Nutmeg", "Clove", "Saffron", "Ginger", "Cumin", "Elemi"},
}

# Star ingredients named in skincare/makeup copy, canonicalised the same way
# so "infused with hyaluronic acid" and "hyaluronic acid duo" meet in one node.
INGREDIENT_VOCAB: list[tuple[str, str]] = [
    ("Hyaluronic Acid", r"hyaluronic|poly h\.?a\b"), ("Niacinamide", r"niacinamide"), ("Vitamin C", r"vitamin c\b"),
    ("Vitamin E", r"vitamin e\b"), ("Retinol", r"retinol"), ("PDRN", r"\bpdrn\b"), ("Peptides", r"\bpeptides?\b"),
    ("Ceramides", r"ceramides?\b"), ("Squalane", r"squalane"), ("Collagen", r"\bcollagen fragment|biotech collagen"),
    ("Rosapeptide", r"rosapeptide"), ("Rose de Granville", r"rose de granville"),
    ("Yquem Golden Sap", r"yquem"), ("Golden Ferment", r"golden ferment"),
    ("OX-C Treatment", r"\box-c\b"), ("Lily Extract", r"\blily extract|lilium"),
    ("Water Lily", r"water lily"), ("Edelweiss Extract", r"edelweiss"), ("Mallow Extract", r"\bmallow\b"),
    ("Longoza Extract", r"longoza"), ("Centella Asiatica", r"centella"), ("Marine Extract", r"marine extract"),
    ("Cherry Oil", r"cherry oil"), ("Cherry Extract", r"cherry extract"), ("Shea Butter", r"shea"),
    ("Jasmine Floral Wax", r"jasmine floral wax"), ("Iris Extract", r"iris extract|extract of iris"),
    ("Rose Extract", r"(?<!granville )rose extract|extract of rose\b"), ("Wild Pansy Extract", r"wild pansy"),
    ("Yarrow Extract", r"yarrow"), ("Peony Extract", r"peony extract|extracts? of peony"),
    ("Pomegranate Flower Extract", r"pomegranate flower"), ("Pistachio Extract", r"pistachio"),
    ("Cornflower Water", r"cornflower"), ("D-Panthenol", r"panthenol"), ("Hibiscus Extract", r"hibiscus"),
    ("Polysaccharides", r"polysaccharide"),
]

# Words that name a family or a texture rather than an ingredient; a note
# title made only of these ("Chypre notes") is not a note.
NON_NOTES = {"chypre", "floral", "fruity", "woody", "ambery", "spicy", "fresh", "oriental", "gourmand",
             "aromatic", "musky", "leathery", "notes", "note", "accord", "accords", "facet", "heart"}

# Descriptions condensed by hand from each product page's own copy, so the
# catalog carries plain advisor-style sentences rather than verbatim marketing
# text. Keyed by catalog id; products not listed here fall back to an
# extractive condensation of the page description.
DESCRIPTIONS: dict[str, str] = {}


# --------------------------------------------------------------------------
# Text helpers


def fold(s: str) -> str:
    """Lowercase, strip accents and unify apostrophes, for name matching."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.replace("’", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


def spoken(s: str) -> str:
    """The form a speech-to-text engine would emit: no punctuation or accents."""
    s = s.replace("’", "'").replace("&", " and ")
    s = fold(s).replace("'", "")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def slugify(s: str) -> str:
    return re.sub(r"-+", "-", spoken(s).replace(" ", "-")).strip("-")


def clean_name(name: str) -> str:
    # One HK tile carries an internal "HK_" market prefix.
    name = re.sub(r"^HK_", "", name.strip())
    return re.sub(r"\s+", " ", name)


def strip_footnotes(s: str) -> str:
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[¹²³⁰-⁹]+", "", s)  # superscript digits
    s = re.sub(r"(?<=[A-Za-z.,)])\*+", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def block_paragraphs(block_html: str) -> list[str]:
    parts = re.split(r"<br\s*/?>\s*(?:<br\s*/?>)?", block_html)
    out = []
    for p in parts:
        p = strip_footnotes(re.sub(r"<[^>]+>", " ", p))
        # Drop footnote lines ("* At Dior.", "1 In vitro test...") and legal notes.
        if not p or len(p) < 25 or re.match(r"^(\*|\d\s|At Dior)", p):
            continue
        out.append(p)
    return out


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z‘“\"'])", text) if s.strip()]


def condense(paragraphs: list[str], limit: int = 320) -> str:
    """Extractive fallback: the first sentences of the page copy, up to ~limit chars."""
    out: list[str] = []
    for p in paragraphs:
        for s in sentences(p):
            if len(" ".join(out + [s])) > limit and out:
                return " ".join(out)
            out.append(s)
            if len(out) >= 3:
                return " ".join(out)
    return " ".join(out)


# --------------------------------------------------------------------------
# Browser


DISCOVER_JS = r"""
() => {
  const out = [];
  document.querySelectorAll('script.product-tile-data').forEach(s => {
    let d; try { d = JSON.parse(s.textContent); } catch (e) { return; }
    if (!d || !d.product) return;
    const p = d.product;
    // Collection pages render tiles without the product-tile__link anchor, so
    // fall back to any link that ends in the master id.
    const tile = s.closest('.product-tile');
    const a = (tile && tile.querySelector('a.product-tile__link'))
           || document.querySelector(`a.product-tile__link[data-pid="${p.masterId}"]`)
           || document.querySelector(`a[href*="-${p.masterId}.html"]`);
    let short = null;
    if (a) {
      const tile = a.closest('[class*="product-tile"]')?.parentElement?.parentElement;
      const sd = tile && tile.querySelector('.product-tile__short-description');
      short = sd ? sd.textContent.replace(/\s+/g, ' ').trim() : null;
    }
    out.push({masterId: p.masterId, name: p.name, collection: p.collection || null,
              axis: p.axis || null, price: p.price ?? null,
              href: a ? a.getAttribute('href') : null, short});
  });
  return out;
}
"""

PRODUCT_JS = r"""
() => {
  const T = el => el ? el.textContent.replace(/\s+/g, ' ').trim() : null;
  const ld = [...document.querySelectorAll('script[type="application/ld+json"]')]
    .map(s => { try { return JSON.parse(s.textContent); } catch (e) { return null; } })
    .filter(Boolean);
  const desc = document.querySelector('#section-description');
  const descBlocks = desc ? [...desc.querySelectorAll('.pdp-description-tabs__text')]
    .map(e => ({html: e.innerHTML, endNote: e.classList.contains('pdp-description-tabs__text--end-note')})) : [];
  const notes = [...document.querySelectorAll('#section-olfactorynotes .olfactory-note')]
    .map(n => ({title: T(n.querySelector('.olfactory-note__title')),
                description: T(n.querySelector('.olfactory-note__description'))}));
  const notesText = T(document.querySelector('#section-olfactorynotes'));
  const carousels = [...document.querySelectorAll('.carousel-section')].map(sec => ({
    surtitle: T(sec.querySelector('.carousel-section__surtitle')),
    title: T(sec.querySelector('.carousel-section__title')),
    cards: [...sec.querySelectorAll('.content-card')].map(c => ({
      title: T(c.querySelector('.content-card__title')),
      description: T(c.querySelector('.content-card__description'))}))}));
  const preload = [...document.querySelectorAll('link[rel="preload"][as="image"]')]
    .map(l => l.getAttribute('href')).filter(Boolean);
  return {
    url: location.href,
    title: T(document.querySelector('h1.pdp-details__title')) || T(document.querySelector('h1')),
    short: T(document.querySelector('.pdp-details__short-description')),
    crumb: T(document.querySelector('.pdp-details__breadcrumb')),
    ld, descBlocks, notes, notesText, carousels, preload,
  };
}
"""


class Browser:
    def __init__(self, executable: str, profile_dir: Path, headful: bool, delay: float):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self.ctx = self._pw.chromium.launch_persistent_context(
            str(profile_dir),
            executable_path=executable,
            headless=not headful,
            user_agent=None if headful else BROWSER_UA,
            locale="en-US",
            viewport={"width": 1366, "height": 900},
            args=["--disable-blink-features=AutomationControlled", "--no-first-run"],
        )
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.delay = delay

    def get(self, url: str, js: str, settle: float = 3.0, retries: int = 2):
        for attempt in range(retries + 1):
            try:
                resp = self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
                status = resp.status if resp else None
                if status == 403:
                    raise RuntimeError("403 from site (bot protection)")
                try:
                    self.page.wait_for_load_state("load", timeout=15000)
                except Exception:
                    pass
                time.sleep(settle)
                data = self.page.evaluate(js)
                time.sleep(self.delay)
                return status, data
            except Exception as exc:  # noqa: BLE001 - network flakiness, retry politely
                print(f"  ! {url}: {exc}", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
        return None, None

    def close(self):
        self.ctx.close()
        self._pw.stop()


# --------------------------------------------------------------------------
# Discovery and selection


def discover(browser: Browser, work: Path) -> list[dict]:
    tiles: list[dict] = []
    for group, paths in LISTING_PAGES.items():
        for path in paths:
            url = SITE + path
            status, data = browser.get(url, DISCOVER_JS)
            data = data or []
            print(f"[list] {status} {path}: {len(data)} tiles")
            for t in data:
                t["group"] = group
                t["listing"] = path
                tiles.append(t)
    (work / "tiles.json").write_text(json.dumps(tiles, indent=1, ensure_ascii=False))
    return tiles


def select(tiles: list[dict], quotas: dict[str, int]) -> dict[str, list[dict]]:
    by_id: dict[str, dict] = {}
    listings: dict[str, set[str]] = {}
    for t in tiles:
        if not t.get("href"):
            continue
        by_id.setdefault(t["masterId"], t)
        listings.setdefault(t["masterId"], set()).add(t["listing"])
    for mid, t in by_id.items():
        t["listings"] = sorted(listings[mid])

    chosen: dict[str, list[dict]] = {}
    taken: set[str] = set()
    for group, quota in quotas.items():
        pool = [t for t in by_id.values() if t["group"] == group]
        picked: list[dict] = []
        for want in PRIORITY[group]:
            for t in pool:
                if t["masterId"] in taken or fold(clean_name(t["name"])) != fold(want):
                    continue
                if EXCLUDE.search(t["name"]) or EXCLUDE.search(t.get("short") or ""):
                    continue
                picked.append(t)
                taken.add(t["masterId"])
                break  # one product per entry; list a name twice to take two
        for t in pool:  # then the rest of the listings, in page order
            if t.get("price") is None:  # bundles and sets carry no single price
                continue
            if t["masterId"] in taken or EXCLUDE.search(t["name"]) or EXCLUDE.search(t.get("short") or ""):
                continue
            picked.append(t)
            taken.add(t["masterId"])
        chosen[group] = picked
    return chosen


# --------------------------------------------------------------------------
# Product parsing


def size_label(raw: str | None) -> str | None:
    if not raw:
        return None
    m = re.match(r"^(\d+)(?:_(\d+))?_([a-z]+)(?:_[a-z]+)?$", raw.strip(), re.I)
    if not m:
        return raw.replace("_", " ").lower()
    whole, frac, unit = m.groups()
    num = whole if not frac or set(frac) == {"0"} else f"{whole}.{frac.rstrip('0')}"
    return f"{num} {unit.lower()}"


def size_sort_key(label: str) -> float:
    m = re.match(r"([\d.]+)", label or "")
    return float(m.group(1)) if m else 0.0


def cdn_image(url: str | None, width: int = 800) -> str | None:
    if not url:
        return None
    url = html.unescape(url)
    if url.startswith("/"):
        url = BASE + url
    url = re.sub(r"\?.*$", "", url)
    return f"{url}?sw={width}"


def line_for(name: str, collection: str | None) -> str:
    f = fold(name)
    if collection and fold(collection) == "la collection privee":
        return "La Collection Privée"
    best = None
    for prefix, line in LINE_PREFIXES:
        if f.startswith(fold(prefix)) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, line)
    if best:
        return best[1]
    if collection and not re.search(r"\b(SK|MU|DA|Core|Frag|Specific)\b", collection):
        return collection
    return name


def fragrance_subcategory(name: str, short: str | None, paragraphs: list[str]) -> str | None:
    for source in (short or "", name):
        f = fold(source)
        for needle, sub in CONCENTRATIONS:
            if needle in f:
                return sub
    # Fall back to the copy, taking whichever concentration it mentions first
    # ("a full and voluptuous perfume essence...").
    f = fold(" ".join(paragraphs))
    hits = [(f.find(needle), -len(needle), sub) for needle, sub in CONCENTRATIONS + [("perfume essence", "essence de parfum")] if needle in f]
    return min(hits)[2] if hits else None


# The HK site serves one product's subtitle in French.
FRENCH_FAMILY = {"hesperidees": "Citrus", "musquees": "Musky", "boisees": "Woody", "florales": "Floral"}


def family_from_short(short: str | None) -> str | None:
    """Olfactory family from the subtitle the page shows under the name,
    e.g. "Eau de Parfum - Solar and Floral Notes" -> "Solar Floral"."""
    if not short:
        return None
    for seg in re.split(r"\s+[-–—]\s+", short):
        seg = seg.strip().rstrip(".")
        m = re.match(r"^(.*?)\s+notes?$", seg, re.I) or re.match(r"^notes?\s+(.*)$", seg, re.I)
        if m:
            words = [w for w in re.split(r"[\s,]+", m.group(1)) if w and fold(w) not in {"and", "&", "et"}]
            words = [FRENCH_FAMILY.get(fold(w), w) for w in words]
            return " ".join(w[:1].upper() + w[1:].lower() for w in words) or None
    return None


def gender_for(crumbs: list[str], line: str, listings: list[str]) -> str:
    if line == "La Collection Privée":
        return "unisex"
    joined = fold(" ".join(crumbs))
    if "women's fragrance" in joined or "womens fragrance" in joined:
        return "women"
    if "men's fragrance" in joined or "mens fragrance" in joined:
        return "men"
    women = any("womens-fragrance" in l for l in listings)
    men = any("mens-fragrance" in l and "womens" not in l for l in listings)
    if women and not men:
        return "women"
    if men and not women:
        return "men"
    return "unisex"


def vocab_matches(text: str, vocab: list[tuple[str, str]]) -> list[str]:
    """Canonical names found in text, in reading order, longest match first."""
    f = fold(text)
    spans = []
    for canon, pattern in vocab:
        for m in re.finditer(pattern, f):
            spans.append((m.start(), -(m.end() - m.start()), m.end(), canon))
    spans.sort()
    out: list[str] = []
    taken_to = -1
    for start, _neg, end, canon in spans:
        if start < taken_to:  # inside a longer match that already claimed this text
            continue
        taken_to = end
        if canon not in out:
            out.append(canon)
    for generic, specifics in GENERIC_NOTES.items():
        if generic in out and any(sp in out for sp in specifics):
            out.remove(generic)
    return out


def parse_notes(raw: dict, short: str | None, paragraphs: list[str]) -> dict:
    """Notes as single canonical ingredients.

    Uses the page's olfactory-notes panel when it has one; otherwise (La
    Collection Privée pages have no panel) the notes the copy itself names.
    Dior's panel lists key notes without saying which are top, heart or base,
    so they all go in "heart" unless a note title labels its tier."""
    notes: dict[str, list[str]] = {"top": [], "heart": [], "base": []}

    def add(tier: str, items: list[str]) -> None:
        for i in items:
            if all(i not in v for v in notes.values()):
                notes[tier].append(i)

    for n in raw.get("notes") or []:
        title = re.sub(r"^HK_", "", strip_footnotes(n.get("title") or ""))
        if not title:
            continue
        tier = "heart"
        m = re.match(r"^(top|head|heart|middle|base)\s+notes?\s*[:\-–]?\s*(.*)$", title, re.I)
        if m:
            tier = {"head": "top", "middle": "heart"}.get(m.group(1).lower(), m.group(1).lower())
            title = m.group(2)
        found = vocab_matches(title, NOTE_VOCAB)
        if not found:
            # Unknown ingredient: keep it as a short title-cased name, unless
            # the title only names a family ("Chypre notes").
            words = [w for w in re.findall(r"[a-z][a-z'-]*", fold(title)) if w not in NON_NOTES]
            if 0 < len(words) <= 3:
                found = [" ".join(w.capitalize() for w in words)]
                print(f"  ? note not in vocabulary, kept as {found[0]!r} ({title!r})", file=sys.stderr)
        add(tier, found)
    if sum(len(v) for v in notes.values()) < 2:
        add("heart", vocab_matches(" ".join([short or ""] + paragraphs), NOTE_VOCAB))
    return notes


def key_ingredients(raw: dict, short: str | None, paragraphs: list[str]) -> list[str]:
    """Star ingredients/technologies the page names, canonicalised.

    Reads the page's "Innovation"/"Active ingredients" cards first, then the
    description copy. A card naming something outside the vocabulary (a
    patented technology) is kept as written, tidied."""
    cards = []
    for car in raw.get("carousels") or []:
        if fold(car.get("surtitle") or "") in INGREDIENT_SECTIONS:
            cards += [c for c in car.get("cards") or [] if c.get("title")]
    out: list[str] = []
    for c in cards:
        found = vocab_matches(c["title"], INGREDIENT_VOCAB)
        if not found:
            title = re.sub(r"[\[\]™®]", "", strip_footnotes(c["title"])).strip()
            title = re.sub(r"^(the|a|an)\s+", "", title, flags=re.I)
            # Skip cards about a texture or a count ("A hybrid texture", "10,000 micro-pearls").
            keep = title and len(title) <= 40 and not re.search(r"\d|texture", title, re.I)
            found = [title[:1].upper() + title[1:]] if keep else []
        out += [f for f in found if f not in out]
    for f in vocab_matches(" ".join([short or ""] + paragraphs), INGREDIENT_VOCAB):
        if f not in out:
            out.append(f)
    return out[:6]


# Normalised product types for makeup and skincare, checked in order against
# the short description and name; the first hit wins.
SUBCATEGORIES = {
    "makeup": [
        (r"lip oil", "lip oil"), (r"\bgloss\b|plumping", "lip gloss"), (r"lip balm|lip treatment", "lip balm"),
        (r"lipstick", "lipstick"), (r"cushion", "cushion foundation"), (r"concealer", "concealer"),
        (r"compact foundation", "compact foundation"), (r"makeup base|primer", "primer"),
        (r"foundation", "foundation"), (r"blush", "blush"), (r"highlighter|luminizer", "highlighter"),
        (r"mascara", "mascara"), (r"eyeshadow|eye palette", "eyeshadow palette"),
        (r"eyeliner|liner", "eyeliner"), (r"nail polish|vernis", "nail polish"),
    ],
    "skincare": [
        (r"\buv\b|\bspf\b", "sunscreen"), (r"\beye\b|yeux|contour", "eye care"),
        (r"cleans|foam|micellar|mousse", "cleanser"), (r"lotion|toner|mist", "lotion"),
        (r"serum|concentrate|\bshot\b|-shot|hyalushot|corrector|huile|nectar|\boil\b", "serum"),
        (r"balm|baume", "balm"), (r"cream|creme|emulsion|\bcare\b", "cream"),
    ],
}


def subcategory_other(category: str, name: str, short: str | None, crumbs: list[str]) -> str | None:
    text = fold(f"{short or ''} {name}")
    for pattern, label in SUBCATEGORIES.get(category, []):
        if re.search(pattern, text):
            return label
    if short:
        return re.split(r"\s+[-–—]\s+", short)[0].strip().lower()
    return crumbs[-1].lower() if crumbs else None


def parse_product(raw: dict, tile: dict) -> dict | None:
    group = next((d for d in raw["ld"] if d.get("@type") == "ProductGroup"), None)
    single = next((d for d in raw["ld"] if d.get("@type") == "Product"), None)
    crumbs_ld = next((d for d in raw["ld"] if d.get("@type") == "BreadcrumbList"), None)
    crumbs = [e["item"]["name"] for e in (crumbs_ld or {}).get("itemListElement", [])]

    variants = (group or {}).get("hasVariant") or ([single] if single else [])
    if not variants:
        return None
    name = clean_name(raw.get("title") or (group or single).get("name") or tile["name"])
    short = raw.get("short") or tile.get("short") or (group or single).get("description")
    short = re.sub(r"^HK_", "", short.strip()) if short else None

    top = fold(crumbs[1]) if len(crumbs) > 1 else ""
    category = (
        "fragrance" if top.startswith("fragrance")
        else "makeup" if top.startswith("makeup") or top.startswith("make-up")
        else "skincare" if top.startswith("skincare")
        else tile["group"]
    )

    paragraphs: list[str] = []
    capacity = None
    for b in raw.get("descBlocks") or []:
        if b.get("endNote"):
            m = re.search(r"Capacity:\s*([^<]+)", b["html"])
            if m:
                capacity = strip_footnotes(m.group(1))
            continue
        paragraphs.extend(block_paragraphs(b["html"]))

    # Sizes: one entry per distinct size; colour-only variants share one entry.
    sizes: dict[str, int | None] = {}
    varies_by = " ".join((group or {}).get("variesBy") or [])
    for v in variants:
        price = (v.get("offers") or {}).get("price")
        price = int(round(float(price))) if price not in (None, "") else None
        label = size_label(v.get("size")) if "size" in varies_by or v.get("size") else None
        label = label or capacity or "standard"
        if label not in sizes or (price is not None and (sizes[label] is None or price < sizes[label])):
            sizes[label] = price
    size_list = [{"label": k, "price_hkd": p} for k, p in sorted(sizes.items(), key=lambda kv: size_sort_key(kv[0]))]
    prices = [s["price_hkd"] for s in size_list if s["price_hkd"] is not None]

    # Hero image: the preloaded product shot when there is one, else the first variant's.
    image = next((u for u in raw.get("preload") or [] if "Sites-master_dior" in u), None)
    image = cdn_image(image or variants[0].get("image"))

    line = line_for(name, tile.get("collection"))
    entry = {
        "id": None,
        "brand": "Dior",
        "name": name,
        "line": line,
        "category": category,
        "subcategory": None,
        "gender": None,
        "family": None,
        "notes": None,
        "key_ingredients": [],
        "description": condense(paragraphs) or (short or ""),
        "sizes": size_list,
        "price_hkd_from": min(prices) if prices else None,
        "image_url": image,
        "url": (group or single).get("url") or (group or single).get("@id") or raw["url"],
        "color_hex": None,
        "aliases": [],
        "stock": 0,
        # Private working fields, stripped before writing.
        "_master": tile["masterId"],
        "_short": short,
        "_shades": [str(v.get("color")) for v in variants if v.get("color")],
    }
    if category == "fragrance":
        entry["subcategory"] = fragrance_subcategory(name, short, paragraphs)
        entry["gender"] = gender_for(crumbs, line, tile.get("listings") or [])
        entry["family"] = family_from_short(short)
        entry["notes"] = parse_notes(raw, short, paragraphs)
    else:
        entry["subcategory"] = subcategory_other(category, name, short, crumbs)
        entry["key_ingredients"] = key_ingredients(raw, short, paragraphs)
    return entry


# --------------------------------------------------------------------------
# Colour, aliases, stock


def image_colour(path: Path) -> str | None:
    """Representative product colour, ignoring the white/pale-grey backdrop.

    If a meaningful share of the product is chromatic (a gold bottle, a red
    lipstick bullet next to its black case), return the median colour of the
    dominant hue band. Otherwise the product is neutral (silver, black, clear
    glass) and the median of all its pixels is the honest answer."""
    import colorsys

    from PIL import Image

    try:
        im = Image.open(path).convert("RGB")
    except Exception:  # noqa: BLE001 - corrupt/blocked download
        return None
    im.thumbnail((200, 200))
    raw = im.tobytes()
    pixels = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
    # Backdrops are white or a pale grey, and their soft shadows are grey too.
    px = [p for p in pixels if not (min(p) > 228 or (max(p) - min(p) < 14 and min(p) > 196))]
    if len(px) < 30:
        return None

    def median(values: list[tuple[int, int, int]]) -> str:
        chans = [sorted(c) for c in zip(*values)]
        return "#%02x%02x%02x" % tuple(c[len(c) // 2] for c in chans)

    bins: dict[int, list[tuple[int, int, int]]] = {}
    for p in px:
        h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in p))
        if s > 0.25 and v > 0.18:
            bins.setdefault(int(h * 24) % 24, []).append(p)
    chromatic = sum(len(b) for b in bins.values())
    if chromatic < 0.05 * len(px):
        return median(px)
    # The busiest hue band, counting its two neighbours (hue is circular).
    best = max(range(24), key=lambda i: sum(len(bins.get((i + d) % 24, [])) for d in (-1, 0, 1)))
    band = [p for d in (-1, 0, 1) for p in bins.get((best + d) % 24, [])]
    return median(band)


def fetch_image(url: str, dest: Path) -> Path | None:
    import httpx

    if dest.exists() and dest.stat().st_size > 0:
        return dest
    try:
        # Default httpx UA on purpose: the CDN 403s a browser UA from a non-browser TLS stack.
        r = httpx.get(url, timeout=30, follow_redirects=True)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            dest.write_bytes(r.content)
            return dest
        print(f"  ! image {r.status_code} {url}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! image {exc} {url}", file=sys.stderr)
    return None


ABBREV = [("eau de parfum", "edp"), ("eau de toilette", "edt")]


def build_aliases(entry: dict) -> list[str]:
    name = spoken(entry["name"])
    out = [name]
    if name.startswith("dior ") and len(name.split()) > 2:
        out.append(name[5:])
    if entry["category"] == "fragrance":
        for long, short in ABBREV:
            if long in name:
                out.append(name.replace(long, short))
        sub = entry.get("subcategory") or ""
        # "hypnotic poison eau de toilette", "gris dior eau de parfum"; only
        # for names that do not already carry a concentration word.
        bare = not re.search(r"\b(parfum|toilette|cologne|eau|extrait|elixir|essence|intense)\b", name)
        if bare and sub in {"eau de parfum", "eau de toilette", "parfum", "esprit de parfum"}:
            out.append(f"{name} {sub}")
            for long, short in ABBREV:
                if sub == long:
                    out.append(f"{name} {short}")
        if entry["line"] == "La Collection Privée":
            out.append(f"{name} la collection privee" if "la collection" not in name else name)
        if "j adore" in name or "jadore" in name:
            out += [a.replace("jadore", "j adore") for a in out if "jadore" in a]
    else:
        for shade in ("999",):
            if shade in entry.get("_shades", []):
                out.append(f"{name} {shade}")
    for alias, target in FLAGSHIP_ALIASES.items():
        if fold(target) == fold(entry["name"]):
            out.append(alias)
    seen, clean = set(), []
    for a in out:
        a = re.sub(r"\s+", " ", a).strip()
        if a and a not in seen and a not in GENERIC_ALIASES and len(a) > 3:
            seen.add(a)
            clean.append(a)
    return clean


def demo_stock(pid: str) -> int:
    """Deterministic demo stock: 0-40 units, roughly one in eight products
    deliberately at 0-3 so "low stock" is easy to show in a demo."""
    h = int(hashlib.sha256(pid.encode()).hexdigest()[:8], 16)
    return h % 4 if h % 8 == 0 else 4 + h % 37


# --------------------------------------------------------------------------
# Main


def validate(catalog: list[dict]) -> None:
    fields = {
        "id": str, "brand": str, "name": str, "line": str, "category": str,
        "subcategory": (str, type(None)), "gender": (str, type(None)),
        "family": (str, type(None)), "notes": (dict, type(None)),
        "key_ingredients": list, "description": str, "sizes": list,
        "price_hkd_from": (int, type(None)), "image_url": (str, type(None)),
        "url": str, "color_hex": (str, type(None)), "aliases": list, "stock": int,
    }
    ids = set()
    for p in catalog:
        assert set(p) == set(fields), f"{p.get('id')}: fields {set(p) ^ set(fields)}"
        for k, t in fields.items():
            assert isinstance(p[k], t), f"{p['id']}.{k} is {type(p[k]).__name__}"
        assert p["id"] not in ids, f"duplicate id {p['id']}"
        ids.add(p["id"])
        assert p["category"] in {"fragrance", "makeup", "skincare"}, p["id"]
        assert p["gender"] in {"women", "men", "unisex", None}, p["id"]
        if p["category"] != "fragrance":
            assert p["family"] is None and p["notes"] is None, p["id"]
        else:
            assert set(p["notes"]) == {"top", "heart", "base"}, p["id"]
        for s in p["sizes"]:
            assert isinstance(s["label"], str) and (s["price_hkd"] is None or isinstance(s["price_hkd"], int))
        assert 0 <= p["stock"] <= 40, p["id"]
        assert all(a == a.lower() and not re.search(r"[^a-z0-9 ]", a) for a in p["aliases"]), p["id"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work-dir", required=True, type=Path, help="scratch dir: browser profile, cache, images")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "backend/app/catalogs/perfume.json")
    ap.add_argument("--browser", help="Chromium-family browser binary (default: Brave, then Helium)")
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--use-cache", action="store_true", help="reuse saved listing tiles and product pages")
    ap.add_argument("--discover-only", action="store_true")
    ap.add_argument("--offline", action="store_true", help="with --use-cache: never open the browser, use only saved pages")
    ap.add_argument("--quota", default="40,20,20", help="fragrance,makeup,skincare counts")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds to pause after each page load")
    args = ap.parse_args()

    work: Path = args.work_dir.resolve()
    (work / "raw").mkdir(parents=True, exist_ok=True)
    (work / "images").mkdir(parents=True, exist_ok=True)
    f, m, s = (int(x) for x in args.quota.split(","))
    quotas = {"fragrance": f, "makeup": m, "skincare": s}

    browser: Browser | None = None

    def get_browser() -> Browser:
        nonlocal browser
        if browser is None:
            exe = args.browser or next((b for b in DEFAULT_BROWSERS if Path(b).exists()), None)
            if not exe:
                sys.exit("No Brave/Helium found; pass --browser /path/to/chromium-family-binary")
            # A fresh throwaway profile inside the work dir, never a personal one.
            browser = Browser(exe, work / "browser-profile", args.headful, args.delay)
        return browser

    try:
        tiles_path = work / "tiles.json"
        if (args.use_cache or args.offline) and tiles_path.exists():
            tiles = json.loads(tiles_path.read_text())
        else:
            tiles = discover(get_browser(), work)
        chosen = select(tiles, quotas)
        for group, picked in chosen.items():
            print(f"[select] {group}: {len(picked)} candidates, taking the first {quotas[group]} that parse")
            for t in picked[: quotas[group]]:
                print(f"    {t['masterId']}  {t['name']}  ({t.get('short') or ''})")
        if args.discover_only:
            return 0

        catalog: list[dict] = []
        for group in ("fragrance", "makeup", "skincare"):
            got = 0
            for tile in chosen[group]:
                if got >= quotas[group]:
                    break
                cache = work / "raw" / f"{tile['masterId']}.json"
                if args.use_cache and cache.exists():
                    raw = json.loads(cache.read_text())
                elif args.offline:
                    continue
                else:
                    url = BASE + tile["href"] if tile["href"].startswith("/") else tile["href"]
                    status, raw = get_browser().get(url, PRODUCT_JS)
                    print(f"[product] {status} {tile['name']}")
                    if not raw or not raw.get("ld"):
                        print(f"  ! no product data for {url}", file=sys.stderr)
                        continue
                    cache.write_text(json.dumps(raw, ensure_ascii=False))
                entry = parse_product(raw, tile)
                if entry:  # pages without product JSON-LD (bundles) are skipped
                    catalog.append(entry)
                    got += 1
    finally:
        if browser is not None:
            browser.close()

    # Two products can share a display name (JOY by Dior comes as an eau de
    # parfum and an intense). Say the concentration, the way the site's
    # listing tiles do, so the advisor and the aliases can tell them apart.
    name_counts: dict[str, int] = {}
    for e in catalog:
        name_counts[fold(e["name"])] = name_counts.get(fold(e["name"]), 0) + 1
    for e in catalog:
        sub = e.get("subcategory")
        if name_counts[fold(e["name"])] > 1 and sub and fold(sub) not in fold(e["name"]):
            e["name"] = f"{e['name']} " + " ".join(
                w if w in {"de", "d'eau"} else w[:1].upper() + w[1:] for w in sub.split()
            )

    # Stable ids: name slug, disambiguated by concentration/subcategory, then master id.
    used: set[str] = set()
    for e in catalog:
        base = "dior-" + slugify(e["name"])
        pid = base
        if pid in used and e.get("subcategory"):
            pid = f"{base}-{slugify(e['subcategory'])}"
        if pid in used:
            pid = f"{base}-{e['_master'].lower()}"
        used.add(pid)
        e["id"] = pid
        if pid in DESCRIPTIONS:
            e["description"] = DESCRIPTIONS[pid]

    for e in catalog:
        if e["image_url"]:
            img = fetch_image(e["image_url"], work / "images" / f"{e['_master']}.jpg")
            e["color_hex"] = image_colour(img) if img else None
            time.sleep(0.5)
        e["aliases"] = build_aliases(e)
        e["stock"] = demo_stock(e["id"])

    # An alias two products both claim would spotlight the wrong one half the
    # time; drop it from both unless it is a deliberate flagship alias.
    owners: dict[str, list[dict]] = {}
    for e in catalog:
        for a in e["aliases"]:
            owners.setdefault(a, []).append(e)
    for a, es in owners.items():
        if len(es) > 1 and a not in FLAGSHIP_ALIASES:
            for e in es:
                e["aliases"].remove(a)

    for e in catalog:
        for k in [k for k in e if k.startswith("_")]:
            del e[k]
    validate(catalog)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
    counts = {c: sum(1 for e in catalog if e["category"] == c) for c in ("fragrance", "makeup", "skincare")}
    print(f"[done] wrote {len(catalog)} products to {args.out}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
