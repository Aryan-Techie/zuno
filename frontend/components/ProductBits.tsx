"use client";

import { useState } from "react";
import { catalogImageUrl, type CatalogProduct, type FragranceNotes } from "@/lib/api";
import { categoryLabel } from "@/lib/catalog";

/**
 * Small presentational pieces shared by the console's spotlight and the
 * dashboard's catalog: the product photo (with a quiet monogram when there
 * is none), the olfactory pyramid, the key ingredients, and the Apple
 * device glyphs. Hand-rolled SVG, like the rest of the app.
 */

export function ProductImage({
  product,
  className,
  size,
}: {
  product: CatalogProduct;
  className?: string;
  /** Hint for the browser's layout before the image arrives. */
  size?: number;
}) {
  const [state, setState] = useState<"loading" | "loaded" | "broken">("loading");
  // No source image means the backend has nothing to serve; skip the 404.
  const hasSource = Boolean(product.image_url) && state !== "broken";
  const placeholder = ["mac", "iphone", "ipad", "accessory", "service"].includes(product.category) ? (
    <DeviceGlyph category={product.category} />
  ) : (
    <span className="monogram">{(product.line || product.name).charAt(0)}</span>
  );
  // The placeholder sits underneath until the photo has actually arrived:
  // the backend fetches each image once on first request, which can take a
  // moment, and a blank white tile in the meantime reads as broken.
  return (
    <div className={`pimg${state === "loaded" ? "" : " empty"} ${className ?? ""}`} aria-hidden={!hasSource || undefined}>
      {state !== "loaded" && placeholder}
      {hasSource && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={catalogImageUrl(product.id)}
          alt={product.name}
          width={size}
          height={size}
          loading="lazy"
          decoding="async"
          className={state === "loaded" ? "in" : ""}
          onLoad={() => setState("loaded")}
          onError={() => setState("broken")}
        />
      )}
    </div>
  );
}

const TIERS: { key: keyof FragranceNotes; label: string; hint: string }[] = [
  { key: "top", label: "Top", hint: "the first minutes" },
  { key: "heart", label: "Heart", hint: "the next hours" },
  { key: "base", label: "Base", hint: "what stays" },
];

/**
 * The olfactory pyramid as a drawn pyramid: three bands, narrow at the top
 * where the bright notes burn off first, wide at the base that lingers. Each
 * band's notes sit beside it on the same baseline.
 */
export function NotesPyramid({ notes, compact = false }: { notes: FragranceNotes; compact?: boolean }) {
  const tiers = TIERS.filter((t) => (notes[t.key] ?? []).length > 0);
  if (tiers.length === 0) return null;
  return (
    <div className={`pyramid${compact ? " compact" : ""}`} aria-label="Olfactory pyramid">
      <svg className="pyramid-shape" viewBox="0 0 90 120" aria-hidden="true" preserveAspectRatio="none">
        {/* A tier the house does not list stays drawn, faintly, so the
            pyramid keeps its shape and the gap reads as "not listed". */}
        <path className={`band b1${notes.top?.length ? "" : " none"}`} d="M45 2 L59.7 38 L30.3 38 Z" />
        <path className={`band b2${notes.heart?.length ? "" : " none"}`} d="M29.5 41 L60.5 41 L75.2 77 L14.8 77 Z" />
        <path className={`band b3${notes.base?.length ? "" : " none"}`} d="M14 80 L76 80 L88 118 L2 118 Z" />
      </svg>
      <div className="pyramid-rows">
        {TIERS.map((t) => (
          <div className="tier" key={t.key}>
            <div className="tier-k">
              {t.label}
              {!compact && <small>{t.hint}</small>}
            </div>
            <div className="tier-v">
              {(notes[t.key] ?? []).length ? (notes[t.key] ?? []).join(", ") : <span className="muted">Not listed</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function KeyIngredients({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="ingredients">
      <div className="ingredients-k">Key ingredients</div>
      <ul>
        {items.map((name) => (
          <li key={name}>
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M8 1.8c2.6 3 4 5.2 4 7.2a4 4 0 0 1-8 0c0-2 1.4-4.2 4-7.2z" />
            </svg>
            {name}
          </li>
        ))}
      </ul>
    </div>
  );
}

const glyph = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.4,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

/** One line-drawn glyph per Apple category, standing in for a photo. */
export function DeviceGlyph({ category, className }: { category: string; className?: string }) {
  const props = { className: `device-glyph ${className ?? ""}`, viewBox: "0 0 64 64", "aria-label": categoryLabel(category), role: "img", ...glyph };
  switch (category) {
    case "mac":
      return (
        <svg {...props}>
          <rect x="12" y="14" width="40" height="27" rx="2.5" />
          <path d="M6 46h52l-3 4H9z" />
          <path d="M29 46.5h6" />
        </svg>
      );
    case "iphone":
      return (
        <svg {...props}>
          <rect x="21" y="6" width="22" height="52" rx="5" />
          <path d="M29 10h6" />
        </svg>
      );
    case "ipad":
      return (
        <svg {...props}>
          <rect x="13" y="7" width="38" height="50" rx="4" />
          <circle cx="32" cy="10.5" r="0.6" />
        </svg>
      );
    case "service":
      return (
        <svg {...props}>
          <path d="M32 7l20 7v13c0 13-8.5 22-20 30C20.5 49 12 40 12 27V14z" />
          <path d="M24 31l6 6 11-12" />
        </svg>
      );
    default:
      // accessory: a pair of earbuds
      return (
        <svg {...props}>
          <path d="M20 14a7 7 0 0 1 7 7v4a5 5 0 0 1-5 5h-1v20a3 3 0 0 1-6 0V21a7 7 0 0 1 5-7z" />
          <path d="M44 14a7 7 0 0 0-7 7v4a5 5 0 0 0 5 5h1v20a3 3 0 0 0 6 0V21a7 7 0 0 0-5-7z" />
        </svg>
      );
  }
}
