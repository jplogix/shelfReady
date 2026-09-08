"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { StoreProduct, api } from "@/lib/api";

export default function StorePage() {
  const [products, setProducts] = useState<StoreProduct[]>([]);
  const [cartCount, setCartCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.storeProducts(), api.cart()])
      .then(([p, c]) => {
        setProducts(p);
        setCartCount(c.items.length);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-amber">Demo storefront · noindex · no payments</p>
          <h1 className="text-3xl text-charcoal">Published products</h1>
        </div>
        <Link href="/store/cart" className="rounded border border-line bg-bg-elevated px-3 py-2 text-sm">
          Cart ({cartCount})
        </Link>
      </div>
      {error && <p className="text-red">{error}</p>}
      {products.length === 0 ? (
        <p className="rounded border border-dashed border-line px-4 py-10 text-center text-ink-muted">
          No published products yet. Process a batch, resolve decisions, then publish.
        </p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((p) => (
            <li key={p.id}>
              <Link
                href={`/store/products/${p.slug}`}
                className="block overflow-hidden rounded border border-line bg-bg-elevated"
              >
                {p.primary_image_path ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={api.mediaUrl(p.primary_image_path)}
                    alt={p.title}
                    className="aspect-square w-full object-cover"
                  />
                ) : (
                  <div className="flex aspect-square items-center justify-center bg-line text-ink-muted">
                    No image
                  </div>
                )}
                <div className="space-y-1 p-3">
                  <div className="text-xs text-ink-muted">{p.brand}</div>
                  <div className="font-medium">{p.title}</div>
                  <div className="tabular-nums">
                    {p.currency} {p.price}
                  </div>
                  <div className="text-xs">{p.available ? "In stock" : "Out of stock"}</div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
