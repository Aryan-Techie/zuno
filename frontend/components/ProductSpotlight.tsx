"use client";

import type { CatalogProduct } from "@/lib/api";
import { priceFrom } from "@/lib/catalog";
import { ProductDetail } from "@/components/ProductDetail";
import { ProductImage, DeviceGlyph } from "@/components/ProductBits";
import { productMode } from "@/lib/catalog";

/**
 * The console's headline moment: the caller (or Zuno) names a product and it
 * comes up on screen while the call carries on. The backend emits a
 * product_spotlight event for it (the show_product tool, or a catalog alias
 * heard in the caller's words); the strip beneath keeps the last few within
 * reach so the operator can bring one back while they compare.
 */
export function ProductSpotlight({
  product,
  recent,
  onPick,
  onClose,
}: {
  product: CatalogProduct;
  /** Most recent first, the current product included. */
  recent: CatalogProduct[];
  onPick: (p: CatalogProduct) => void;
  onClose: () => void;
}) {
  return (
    <section className="spotlight" aria-label={`On screen: ${product.name}`} aria-live="polite" key={product.id}>
      <ProductDetail
        product={product}
        variant="spotlight"
        eyebrow={
          <>
            <span className="spot-dot" aria-hidden="true" />
            On screen now
          </>
        }
        aside={
          <button className="spot-close" onClick={onClose} title="Hide until the next product is named" aria-label="Hide product">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        }
      />
      {recent.length > 1 && (
        <div className="spot-strip" role="list" aria-label="Recently shown">
          <span className="spot-strip-k">Recently shown</span>
          {recent.map((p) => (
            <button
              key={p.id}
              role="listitem"
              className={`spot-thumb${p.id === product.id ? " on" : ""}`}
              onClick={() => onPick(p)}
              aria-current={p.id === product.id}
              title={p.name}
            >
              {productMode(p) === "apple" ? (
                <span className="pimg empty">
                  <DeviceGlyph category={p.category} />
                </span>
              ) : (
                <ProductImage product={p} size={40} />
              )}
              <span className="spot-thumb-t">
                <b>{p.name}</b>
                <small>{priceFrom(p) ?? ""}</small>
              </span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
