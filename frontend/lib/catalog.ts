import type { CatalogProduct, CatalogSize, Mode } from "@/lib/api";

/**
 * Presentation helpers for catalog products, shared by the console's
 * spotlight and the dashboard's catalog browser so a price or a category
 * reads the same on both surfaces.
 */

const APPLE_CATEGORIES = new Set(["mac", "iphone", "ipad", "accessory", "service"]);

export function productMode(p: CatalogProduct): Mode {
  return p.brand?.toLowerCase() === "apple" || APPLE_CATEGORIES.has(p.category) ? "apple" : "perfume";
}

const HKD = new Intl.NumberFormat("en-HK", { maximumFractionDigits: 0 });
const USD = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function formatPrice(amount: number | null | undefined, currency: "HKD" | "USD"): string | null {
  if (amount == null || Number.isNaN(amount)) return null;
  return currency === "HKD" ? `HK$${HKD.format(amount)}` : `$${USD.format(amount)}`;
}

export function currencyOf(p: CatalogProduct): "HKD" | "USD" {
  return productMode(p) === "apple" ? "USD" : "HKD";
}

export function priceFrom(p: CatalogProduct): string | null {
  const currency = currencyOf(p);
  const from = currency === "USD" ? p.price_usd_from : p.price_hkd_from;
  if (from != null) return formatPrice(from, currency);
  // Some rows only price their sizes; the cheapest one is the honest "from".
  const prices = (p.sizes ?? []).map((s) => sizePrice(s, currency)).filter((x): x is number => x != null);
  return prices.length ? formatPrice(Math.min(...prices), currency) : null;
}

export function sizePrice(s: CatalogSize, currency: "HKD" | "USD"): number | null {
  const v = currency === "USD" ? s.price_usd : s.price_hkd;
  return v == null ? null : v;
}

const CATEGORY_LABEL: Record<string, string> = {
  fragrance: "Fragrance",
  makeup: "Makeup",
  skincare: "Skincare",
  mac: "Mac",
  iphone: "iPhone",
  ipad: "iPad",
  accessory: "Accessories",
  service: "Services",
};

export function categoryLabel(category: string): string {
  return CATEGORY_LABEL[category] ?? category.charAt(0).toUpperCase() + category.slice(1);
}

/** "Eau de Parfum", "Lip Balm" - title case for a lowercase subcategory. */
export function titleCase(text: string | null | undefined): string {
  if (!text) return "";
  const small = new Set(["de", "du", "la", "le", "of", "and", "for", "à"]);
  return text
    .split(/\s+/)
    .map((w, i) => (i > 0 && small.has(w.toLowerCase()) ? w.toLowerCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

/** The subcategory, unless it only repeats the category ("mac" under Mac). */
export function subcategoryLabel(p: CatalogProduct): string {
  const sub = titleCase(p.subcategory);
  if (!sub) return "";
  const same = sub.toLowerCase() === p.category.toLowerCase() || sub.toLowerCase() === categoryLabel(p.category).toLowerCase();
  return same ? "" : sub;
}

/** Line, concentration and who it is made for, as one quiet byline. */
export function productByline(p: CatalogProduct): string {
  const parts = [p.line && p.line !== p.name ? p.line : null, subcategoryLabel(p), p.family, genderLabel(p.gender)];
  return parts.filter(Boolean).join(" · ");
}

export function genderLabel(g: CatalogProduct["gender"]): string | null {
  if (g === "women") return "For her";
  if (g === "men") return "For him";
  if (g === "unisex") return "Unisex";
  return null;
}

export function stockLabel(stock: number | null | undefined): { text: string; tone: "good" | "warn" | "bad" } | null {
  if (stock == null) return null;
  if (stock === 0) return { text: "Out of stock", tone: "bad" };
  if (stock <= 5) return { text: `${stock} left`, tone: "warn" };
  return { text: `${stock} in stock`, tone: "good" };
}

/** A valid #rrggbb, or null - color_hex comes from a scraper and may be off. */
export function safeHex(hex: string | null | undefined): string | null {
  return hex && /^#[0-9a-f]{6}$/i.test(hex) ? hex : null;
}

export type ProductShape = "flacon" | "amphora" | "lipstick" | "jar" | "compact" | "serum";

/**
 * Which procedural object stands in for the product in 3D. Not a replica of
 * any real bottle - just enough silhouette that a fragrance reads as a
 * fragrance and a lipstick as a lipstick while the call goes on.
 */
export function productShape(p: CatalogProduct): ProductShape {
  const sub = `${p.subcategory ?? ""} ${p.name}`.toLowerCase();
  if (p.category === "fragrance") {
    const line = `${p.line ?? ""} ${p.name}`.toLowerCase();
    return /j.?adore|poison|hypnotic|dune|addict/.test(line) ? "amphora" : "flacon";
  }
  if (p.category === "makeup") {
    if (/lip|rouge|gloss|balm/.test(sub)) return "lipstick";
    if (/powder|blush|compact|cushion|palette|eyeshadow|highlight|bronzer|couleur/.test(sub)) return "compact";
    return "serum";
  }
  if (p.category === "skincare") {
    if (/cream|crème|creme|balm|mask|baume/.test(sub)) return "jar";
    return "serum";
  }
  return "flacon";
}
