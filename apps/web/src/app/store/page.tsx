"use client";

import { useCallback, useEffect, useState } from "react";
import { ProductGrid } from "@/components/ProductCard";
import { EmptyState, ErrorState } from "@/components/RequestState";
import { StoreProduct, api } from "@/lib/api";

export default function StorePage() {
  const [products, setProducts] = useState<StoreProduct[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setProducts(await api.storeProducts());
    } catch (e) {
      setProducts(null);
      setError(e instanceof Error ? e.message : "Could not load the demo store.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-wide text-ink-muted">Demo storefront · noindex · no payments</p>
        <h1 className="text-3xl text-charcoal">Seiko demonstration collection</h1>
        <p className="mt-2 max-w-2xl text-ink-muted">
          Independent ShelfReady demonstration using Seiko 5 Sports references. Not affiliated with, sponsored
          by, or endorsed by Seiko Watch Corporation. Prices and stock are merchant fixture values.
        </p>
      </div>
      {error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : products === null ? (
        <p className="text-ink-muted">Loading published products…</p>
      ) : products.length === 0 ? (
        <EmptyState>
          No featured demonstration products yet. Process the Seiko catalog in the operator workspace, resolve
          decisions, then publish.
        </EmptyState>
      ) : (
        <ProductGrid products={products} />
      )}
    </div>
  );
}
