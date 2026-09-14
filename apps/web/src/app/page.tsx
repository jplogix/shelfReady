"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ProductGrid } from "@/components/ProductCard";
import { EmptyState, ErrorState } from "@/components/RequestState";
import { ModeInfo, StoreProduct, api } from "@/lib/api";

export default function HomePage() {
  const [products, setProducts] = useState<StoreProduct[] | null>(null);
  const [mode, setMode] = useState<ModeInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [list, modeInfo] = await Promise.all([api.storeProducts(), api.mode()]);
      setProducts(list);
      setMode(modeInfo);
    } catch (e) {
      setProducts(null);
      setError(e instanceof Error ? e.message : "Could not load published products.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="space-y-10">
      <section className="space-y-3">
        <p className="text-sm uppercase tracking-[0.14em] text-ink-muted">Demo storefront · noindex · no payments</p>
        <h1 className="max-w-2xl text-4xl text-charcoal md:text-5xl">
          From messy supplier data to storefront-ready products.
        </h1>
        <p className="max-w-xl text-lg text-ink-muted">
          These listings were prepared from a supplier spreadsheet of Seiko 5 Sports references.
          Independent demonstration — not affiliated with Seiko. Original rows, accepted corrections,
          and supporting evidence are visible on each product.
        </p>
        {mode && (
          <p className="max-w-xl text-sm text-ink-muted">
            Current execution mode: <span className="font-medium text-ink">{mode.label}</span>
            {mode.is_replay
              ? " — deterministic fixture path through the same services, not a live model call."
              : mode.lookup_is_replay
                ? " — live Strands assessments with replay catalog lookup."
                : " — live Strands assessments with live catalog lookup."}
          </p>
        )}
        <div className="flex flex-wrap gap-3 pt-2">
          <Link
            href="/store"
            className="inline-flex min-h-11 items-center rounded border border-green bg-green px-4 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-charcoal"
          >
            Browse published products
          </Link>
          <Link
            href="/workspace"
            className="inline-flex min-h-11 items-center rounded border border-line bg-bg-elevated px-4 text-sm font-medium"
          >
            Operator workspace
          </Link>
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-xl">Published demonstration catalog</h2>
        {error ? (
          <ErrorState message={error} onRetry={refresh} />
        ) : products === null ? (
          <p className="text-ink-muted">Loading published products…</p>
        ) : products.length === 0 ? (
          <EmptyState>
            No products have been published yet. Operator publishing is required before listings appear
            here.
          </EmptyState>
        ) : (
          <ProductGrid products={products} />
        )}
      </section>
    </div>
  );
}
