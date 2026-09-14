"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorState } from "@/components/RequestState";
import { StoreProduct, api } from "@/lib/api";
import { fieldLabel } from "@/lib/field-labels";
import { notifyCartChanged } from "@/lib/shopper-cart";

const SPEC_LABELS: Record<string, string> = {
  manufacturer_reference: "Manufacturer reference",
  collection: "Collection",
  movement_type: "Movement type",
  caliber: "Caliber",
  power_reserve: "Power reserve",
  case_material: "Case material",
  case_diameter: "Case diameter",
  case_thickness: "Case thickness",
  lug_to_lug: "Lug-to-lug",
  lug_width: "Lug width",
  crystal: "Crystal",
  bracelet_material: "Bracelet / strap",
  water_resistance: "Water resistance",
  weight: "Weight",
};

export default function StoreProductPage() {
  const params = useParams();
  const slug = params.slug as string;
  const [product, setProduct] = useState<StoreProduct | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    api
      .storeProduct(slug)
      .then((p) => {
        setProduct(p);
        setError(null);
      })
      .catch((e) => {
        setProduct(null);
        setError(e instanceof Error ? e.message : "This product could not be loaded.");
      });
  }, [slug]);

  async function add() {
    if (!product) return;
    if (!product.available) {
      setError("This product is out of stock.");
      return;
    }
    setAdding(true);
    try {
      await api.addToCart(product.id);
      notifyCartChanged();
      setMessage("Added to cart");
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add this product to the cart.");
    } finally {
      setAdding(false);
    }
  }

  if (error && !product) {
    return <ErrorState title="Product unavailable" message={error} />;
  }
  if (!product) return <p className="text-ink-muted">Loading product…</p>;

  const primary = product.images.find((img) => img.is_primary) || product.images[0];
  const caption = product.image_caption || primary?.caption;
  const suitability = product.image_suitability || primary?.suitability;
  const specs = product.specifications || [];

  return (
    <div className="grid gap-8 md:grid-cols-2">
      <div>
        {product.primary_image_path ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={api.mediaUrl(product.primary_image_path)}
            alt={primary?.alt || product.title}
            className="aspect-square w-full rounded border border-line bg-bg object-contain"
          />
        ) : (
          <div className="flex aspect-square items-center justify-center rounded border border-line bg-line">
            No image
          </div>
        )}
        {caption && (
          <p className="mt-2 text-xs text-ink-muted">
            {caption}
            {suitability === "source_model_match"
              ? " Source/model association was checked against the manufacturer page."
              : suitability === "category_mismatch"
                ? " Image loaded, but it does not match this product category."
                : suitability === "category_match"
                  ? " Category-matching demonstration image."
                  : ""}
          </p>
        )}
        <ul className="mt-3 flex gap-2 overflow-x-auto">
          {product.images?.map((img, i) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={`${img.path}-${i}`}
              src={api.mediaUrl(img.path)}
              alt={img.alt || product.title}
              className="h-20 w-20 rounded border border-line bg-bg object-contain"
              loading="lazy"
            />
          ))}
        </ul>
      </div>
      <div className="space-y-4">
        <p className="text-xs uppercase tracking-wide text-ink-muted">
          noindex demo · not a live marketplace listing · not Seiko-sponsored
        </p>
        <p className="text-sm text-ink-muted">{product.brand}</p>
        <h1 className="text-3xl text-charcoal">{product.title}</h1>
        <p className="text-xl tabular-nums">
          {product.currency} {product.price}
          <span className="ml-2 text-sm font-normal text-ink-muted">merchant demo price</span>
        </p>
        <p className="text-sm">{product.available ? `In stock (${product.stock})` : "Out of stock"}</p>
        <p className="text-ink-muted">{product.description}</p>
        {specs.length > 0 && (
          <table className="w-full text-sm">
            <caption className="sr-only">Supported specifications</caption>
            <tbody>
              {specs.map((row) => (
                <tr key={row.field} className="border-t border-line">
                  <th scope="row" className="py-2 pr-3 text-left font-medium text-ink-muted">
                    {SPEC_LABELS[row.field] || fieldLabel(row.field)}
                  </th>
                  <td className="py-2">{row.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {product.sku && <p className="text-sm text-ink-muted">SKU {product.sku}</p>}
        <button
          type="button"
          onClick={add}
          disabled={!product.available || adding}
          aria-label={`Add ${product.title} to cart`}
          className="min-h-11 rounded bg-charcoal px-4 text-sm text-bg-elevated disabled:opacity-40"
        >
          {adding ? "Adding…" : "Add to cart"}
        </button>
        {message && (
          <p className="text-green" role="status" aria-live="polite">
            {message}
          </p>
        )}
        {error && product && (
          <p className="text-sm text-red" role="alert">
            {error}
          </p>
        )}
        <div className="flex flex-col gap-2 text-sm">
          <Link href={`/store/products/${product.slug}/prepared`} className="font-medium underline">
            See how this listing was prepared
          </Link>
          <Link href="/store/cart" className="underline">
            View cart
          </Link>
        </div>
      </div>
    </div>
  );
}
