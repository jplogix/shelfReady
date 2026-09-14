"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorState } from "@/components/RequestState";
import { StoreProduct, api } from "@/lib/api";
import { addShopperItem } from "@/lib/shopper-cart";

export default function StoreProductPage() {
  const params = useParams();
  const slug = params.slug as string;
  const [product, setProduct] = useState<StoreProduct | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  function add() {
    if (!product) return;
    if (!product.available) {
      setError("This product is out of stock.");
      return;
    }
    addShopperItem({
      store_product_id: product.id,
      slug: product.slug,
      title: product.title,
      price: product.price,
      currency: product.currency,
      image: product.primary_image_path,
    });
    setMessage("Added to cart");
    setError(null);
  }

  if (error && !product) {
    return <ErrorState title="Product unavailable" message={error} />;
  }
  if (!product) return <p className="text-ink-muted">Loading product…</p>;

  return (
    <div className="grid gap-8 md:grid-cols-2">
      <div>
        {product.primary_image_path ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={api.mediaUrl(product.primary_image_path)}
            alt={product.title}
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
              key={`${img.path}-${i}`}
              src={api.mediaUrl(img.path)}
              alt={img.alt || product.title}
              className="h-20 w-20 rounded border border-line object-cover"
              loading="lazy"
            />
          ))}
        </ul>
      </div>
      <div className="space-y-4">
        <p className="text-xs uppercase tracking-wide text-ink-muted">noindex demo · not a live marketplace listing</p>
        <p className="text-sm text-ink-muted">{product.brand}</p>
        <h1 className="text-3xl text-charcoal">{product.title}</h1>
        <p className="text-xl tabular-nums">
          {product.currency} {product.price}
        </p>
        <p className="text-sm">{product.available ? `In stock (${product.stock})` : "Out of stock"}</p>
        <p className="text-ink-muted">{product.description}</p>
        {product.sku && <p className="text-sm text-ink-muted">SKU {product.sku}</p>}
        <button
          type="button"
          onClick={add}
          disabled={!product.available}
          className="min-h-11 rounded bg-charcoal px-4 text-sm text-bg-elevated disabled:opacity-40"
        >
          Add to cart
        </button>
        {message && <p className="text-green">{message}</p>}
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
