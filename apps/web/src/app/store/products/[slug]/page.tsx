"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { StoreProduct, api } from "@/lib/api";

export default function StoreProductPage() {
  const params = useParams();
  const slug = params.slug as string;
  const [product, setProduct] = useState<StoreProduct | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .storeProduct(slug)
      .then(setProduct)
      .catch((e) => setError(e instanceof Error ? e.message : "Not found"));
  }, [slug]);

  async function add() {
    if (!product) return;
    try {
      await api.addToCart(product.id);
      setMessage("Added to cart");
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add to cart");
    }
  }

  if (error && !product) return <p className="text-red">{error}</p>;
  if (!product) return <p className="text-ink-muted">Loading…</p>;

  return (
    <div className="grid gap-8 md:grid-cols-2">
      <div>
        {product.primary_image_path ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={api.mediaUrl(product.primary_image_path)}
            alt={String(product.seo?.image_alt || product.title)}
            className="aspect-square w-full rounded border border-line object-cover"
          />
        ) : (
          <div className="flex aspect-square items-center justify-center rounded border border-line bg-line">
            No image
          </div>
        )}
        <ul className="mt-3 flex gap-2 overflow-x-auto">
          {product.images?.map((img, i) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={i}
              src={api.mediaUrl(img.path)}
              alt={img.alt || product.title}
              className="h-20 w-20 rounded border border-line object-cover"
            />
          ))}
        </ul>
      </div>
      <div className="space-y-4">
        <p className="text-xs text-amber">noindex demo · not a live marketplace listing</p>
        <p className="text-sm text-ink-muted">{product.brand}</p>
        <h1 className="text-3xl text-charcoal">{product.title}</h1>
        <p className="text-xl tabular-nums">
          {product.currency} {product.price}
        </p>
        <p className="text-sm">{product.available ? `In stock (${product.stock})` : "Out of stock"}</p>
        <p className="text-ink-muted">{product.description}</p>
        <p className="text-sm">Variant SKU: {product.variant_sku}</p>
        <button
          type="button"
          onClick={add}
          disabled={!product.available}
          className="rounded bg-charcoal px-4 py-2.5 text-sm text-bg-elevated disabled:opacity-40"
        >
          Add to cart
        </button>
        {message && <p className="text-green">{message}</p>}
        {error && <p className="text-red">{error}</p>}
        <Link href="/store/cart" className="block text-sm underline">
          View cart
        </Link>
        <details className="rounded border border-line bg-bg-elevated p-3 text-sm">
          <summary>Structured data (JSON-LD) preview</summary>
          <pre className="mt-2 overflow-auto text-xs">{JSON.stringify(product.json_ld, null, 2)}</pre>
        </details>
      </div>
    </div>
  );
}
