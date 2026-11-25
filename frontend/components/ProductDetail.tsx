"use client";

import type { ReactNode } from "react";
import type { CatalogProduct } from "@/lib/api";
import {
  categoryLabel,
  currencyOf,
  formatPrice,
  priceFrom,
  productByline,
  productMode,
  sizePrice,
  stockLabel,
  subcategoryLabel,
} from "@/lib/catalog";
import { ProductViewer3D } from "@/components/ProductViewer3D";
import { DeviceGlyph, KeyIngredients, NotesPyramid, ProductImage } from "@/components/ProductBits";

/**
 * One product, large: the 3D stage on the left (a device glyph for Apple,
 * which has no procedural model), everything a caller might ask about on the
 * right. Used by the console's spotlight and the dashboard's detail view, so
 * a product looks the same wherever it is shown.
 */
export function ProductDetail({
  product,
  eyebrow,
  aside,
  variant = "full",
  footer,
}: {
  product: CatalogProduct;
  /** Small line above the name; defaults to category and subcategory. */
  eyebrow?: ReactNode;
  /** Rendered at the top right of the body - a close button, say. */
  aside?: ReactNode;
  /** "spotlight" is the denser cut that shares the console with the call. */
  variant?: "spotlight" | "full";
  /** Rendered at the foot of the body. */
  footer?: ReactNode;
}) {
  const apple = productMode(product) === "apple";
  const currency = currencyOf(product);
  const from = priceFrom(product);
  const stock = stockLabel(product.stock);
  const sizes = (product.sizes ?? []).filter((s) => s.label);
  const byline = productByline(product);

  return (
    <article className={`pdetail${variant === "spotlight" ? " dense" : ""}${apple ? " apple" : " beauty"}`} data-category={product.category}>
      <div className="pdetail-stage">
        {apple ? (
          <div className="apple-stage">
            <DeviceGlyph category={product.category} />
            <span>{categoryLabel(product.category)}</span>
          </div>
        ) : (
          <ProductViewer3D key={product.id} product={product} />
        )}
      </div>

      <div className="pdetail-body">
        <div className="pdetail-top">
          <div className="pdetail-eyebrow">
            {eyebrow ?? [categoryLabel(product.category), subcategoryLabel(product)].filter(Boolean).join(" · ")}
          </div>
          {aside}
        </div>

        <div className="pdetail-head">
          <div className="pdetail-titles">
            <h2 className="pdetail-name">{product.name}</h2>
            {byline && <div className="pdetail-by">{byline}</div>}
            <div className="pdetail-price">
              {from ? (
                <>
                  <span className="k">{sizes.length > 1 ? "From" : "Price"}</span>
                  <b>{from}</b>
                </>
              ) : (
                <span className="k">Price on request</span>
              )}
              {stock && <span className={`pill ${stock.tone}`}>{stock.text}</span>}
            </div>
          </div>
          {!apple && <ProductImage product={product} className="pdetail-photo" size={96} />}
        </div>

        {sizes.length > 0 && (
          <ul className="sizes" aria-label="Sizes">
            {sizes.map((s) => {
              const price = formatPrice(sizePrice(s, currency), currency);
              return (
                <li key={s.label}>
                  <span>{s.label}</span>
                  {price && <b>{price}</b>}
                </li>
              );
            })}
          </ul>
        )}

        {product.category === "fragrance" && product.notes && (
          <NotesPyramid notes={product.notes} compact={variant === "spotlight"} />
        )}
        {(product.category === "makeup" || product.category === "skincare") && (
          <KeyIngredients items={product.key_ingredients ?? []} />
        )}

        {product.description && <p className="pdetail-desc">{product.description}</p>}
        {footer}
      </div>
    </article>
  );
}
