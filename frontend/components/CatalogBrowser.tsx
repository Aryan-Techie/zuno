"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchCatalog, isMissing, MODES, type CatalogProduct, type Mode } from "@/lib/api";
import { categoryLabel, priceFrom, stockLabel, subcategoryLabel } from "@/lib/catalog";
import { MODE_LABEL } from "@/lib/mode";
import { ProductDetail } from "@/components/ProductDetail";
import { ProductImage } from "@/components/ProductBits";

/** Category order per mode, so the chips read in shop order, not JSON order. */
const CATEGORY_ORDER: Record<Mode, string[]> = {
  apple: ["mac", "iphone", "ipad", "accessory", "service"],
  perfume: ["fragrance", "makeup", "skincare"],
};

type Load = { state: "loading" } | { state: "ready"; products: CatalogProduct[] } | { state: "missing" } | { state: "error"; message: string };

/**
 * Both catalogs Zuno sells from - what she can put on the console's screen
 * mid-call. A tab per mode (the Dior tab wears the perfume theme), a
 * category filter and a search over names, lines and spoken aliases, and a
 * detail view with the same 3D stage the spotlight uses.
 *
 * Public endpoints, fetched once per mode and filtered here so typing is
 * instant. A backend without /api/catalog yet gets a calm empty state.
 */
export function CatalogBrowser() {
  const [mode, setMode] = useState<Mode>("apple");
  const [loads, setLoads] = useState<Partial<Record<Mode, Load>>>({});
  const [category, setCategory] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<CatalogProduct | null>(null);

  const load = useCallback(async (m: Mode) => {
    setLoads((prev) => ({ ...prev, [m]: { state: "loading" } }));
    try {
      const res = await fetchCatalog(m);
      setLoads((prev) => ({ ...prev, [m]: { state: "ready", products: res.products ?? [] } }));
    } catch (e) {
      setLoads((prev) => ({
        ...prev,
        [m]: isMissing(e) ? { state: "missing" } : { state: "error", message: e instanceof Error ? e.message : String(e) },
      }));
    }
  }, []);

  useEffect(() => {
    if (!loads[mode]) void load(mode);
  }, [mode, loads, load]);

  const current = loads[mode] ?? { state: "loading" as const };
  const products = current.state === "ready" ? current.products : [];

  const categories = useMemo(() => {
    const present = new Set(products.map((p) => p.category));
    const ordered = CATEGORY_ORDER[mode].filter((c) => present.has(c));
    const extra = Array.from(present).filter((c) => !CATEGORY_ORDER[mode].includes(c)).sort();
    return [...ordered, ...extra];
  }, [products, mode]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return products.filter((p) => {
      if (category !== "all" && p.category !== category) return false;
      if (!q) return true;
      const hay = [p.name, p.line, p.subcategory, p.family, ...(p.aliases ?? []), ...(p.key_ingredients ?? [])]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [products, category, query]);

  const switchMode = (m: Mode) => {
    setMode(m);
    setCategory("all");
  };

  return (
    <section className="catalog" id="catalog" data-mode={mode === "perfume" ? "perfume" : undefined}>
      <div className="cat-head">
        <div>
          <h2>{mode === "perfume" ? "The Dior beauty catalog" : "The Apple catalog"}</h2>
          <p>
            {mode === "perfume"
              ? "Fragrance first, then makeup and skincare. Demo. Not affiliated with Dior."
              : "Macs, iPhones, iPads, accessories and services, priced in USD."}
            {current.state === "ready" && ` ${products.length} products.`}
          </p>
        </div>
        <div className="seg" role="tablist" aria-label="Catalog">
          {MODES.map((m) => (
            <button key={m} role="tab" aria-selected={m === mode} onClick={() => switchMode(m)}>
              {MODE_LABEL[m]}
            </button>
          ))}
        </div>
      </div>

      {current.state === "ready" && products.length > 0 && (
        <div className="cat-tools">
          <input
            className="cat-search"
            type="search"
            placeholder={mode === "perfume" ? "Search a name, a note, an ingredient…" : "Search a product…"}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search the catalog"
          />
          <div className="cat-chips" role="group" aria-label="Category">
            <button aria-pressed={category === "all"} onClick={() => setCategory("all")}>
              All
            </button>
            {categories.map((c) => (
              <button key={c} aria-pressed={category === c} onClick={() => setCategory(c)}>
                {categoryLabel(c)}
              </button>
            ))}
          </div>
        </div>
      )}

      {current.state === "loading" && (
        <div className="cat-grid" aria-busy="true">
          {Array.from({ length: 5 }).map((_, i) => (
            <div className="cat-skel" key={i} />
          ))}
        </div>
      )}
      {current.state === "missing" && (
        <p className="cat-empty">
          <b>No catalog here yet</b>
          This backend does not serve /api/catalog for {MODE_LABEL[mode]}. Once it does, the products show up here.
        </p>
      )}
      {current.state === "error" && (
        <p className="cat-empty">
          <b>The catalog didn’t load</b>
          {current.message}.{" "}
          <button className="ghost" onClick={() => void load(mode)}>
            Try again
          </button>
        </p>
      )}
      {current.state === "ready" && products.length === 0 && (
        <p className="cat-empty">
          <b>The {MODE_LABEL[mode]} catalog is empty</b>
          Nothing to show yet.
        </p>
      )}
      {current.state === "ready" && products.length > 0 && shown.length === 0 && (
        <p className="cat-empty">
          <b>Nothing matches</b>
          Try another word, or clear the category.
        </p>
      )}
      {shown.length > 0 && (
        <div className="cat-grid">
          {shown.map((p, i) => (
            <CatalogCard key={p.id} product={p} index={i} onOpen={() => setOpen(p)} />
          ))}
        </div>
      )}

      {open && <ProductModal product={open} mode={mode} onClose={() => setOpen(null)} />}
    </section>
  );
}

function CatalogCard({ product, index, onOpen }: { product: CatalogProduct; index: number; onOpen: () => void }) {
  const stock = stockLabel(product.stock);
  const sub = subcategoryLabel(product) || categoryLabel(product.category);
  return (
    <button
      className="cat-card"
      onClick={onOpen}
      style={{ animationDelay: `${Math.min(index, 12) * 25}ms` }}
      aria-label={`${product.name}, ${priceFrom(product) ?? "price on request"}. Open details.`}
    >
      <ProductImage product={product} />
      <span className="cat-card-body">
        <span className="cat-card-k">{product.line && product.line !== product.name ? `${product.line} · ${sub}` : sub}</span>
        <span className="cat-card-name">{product.name}</span>
        <span className="cat-card-foot">
          <b>{priceFrom(product) ?? "—"}</b>
          {stock && <small className={stock.tone === "good" ? "" : stock.tone}>{stock.text}</small>}
        </span>
      </span>
    </button>
  );
}

/**
 * The detail view: the same large card the console's spotlight shows, over
 * the page. Escape or a click outside closes it; focus goes to the close
 * button on open and back to where it was on close.
 */
function ProductModal({ product, mode, onClose }: { product: CatalogProduct; mode: Mode; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      previous?.focus?.();
    };
  }, [onClose]);

  return (
    <div className="pmodal" onClick={onClose} role="presentation">
      <div
        className="pmodal-card"
        role="dialog"
        aria-modal="true"
        aria-label={product.name}
        data-mode={mode === "perfume" ? "perfume" : undefined}
        onClick={(e) => e.stopPropagation()}
      >
        <ProductDetail
          product={product}
          aside={
            <button ref={closeRef} className="spot-close" onClick={onClose} aria-label="Close">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          }
          footer={mode === "perfume" ? <p className="fineprint">Demo. Not affiliated with Dior.</p> : undefined}
        />
      </div>
    </div>
  );
}
