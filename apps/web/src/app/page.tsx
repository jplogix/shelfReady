"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, Batch } from "@/lib/api";
import { statusColor } from "@/lib/api";

export default function HomePage() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setBatches(await api.batches());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load batches");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function loadSample() {
    setBusy(true);
    try {
      const batch = await api.loadSample();
      await refresh();
      window.location.href = `/batches/${batch.id}`;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sample load failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <p className="text-sm uppercase tracking-[0.14em] text-ink-muted">Commerce operations</p>
        <h1 className="max-w-2xl text-4xl text-charcoal md:text-5xl">
          From messy supplier data to storefront-ready products.
        </h1>
        <p className="max-w-xl text-lg text-ink-muted">
          Import a catalog, inspect corrections, resolve exceptions, publish to the demo store, and verify
          purchasability — an agent that does the work.
        </p>
        <div className="flex flex-wrap gap-3 pt-2">
          <button
            type="button"
            onClick={loadSample}
            disabled={busy}
            className="rounded bg-charcoal px-4 py-2.5 text-sm font-medium text-bg-elevated disabled:opacity-60"
          >
            {busy ? "Loading sample…" : "Load sample supplier batch"}
          </button>
          <Link
            href="/import"
            className="rounded border border-line bg-bg-elevated px-4 py-2.5 text-sm font-medium"
          >
            Import CSV
          </Link>
        </div>
      </section>

      {error && (
        <div className="rounded border border-red/30 bg-red-soft px-4 py-3 text-sm text-red" role="alert">
          {error}
          <button type="button" className="ml-3 underline" onClick={refresh}>
            Retry
          </button>
        </div>
      )}

      <section>
        <h2 className="mb-4 text-2xl">Batches</h2>
        {loading ? (
          <p className="text-ink-muted">Loading…</p>
        ) : batches.length === 0 ? (
          <p className="rounded border border-dashed border-line bg-bg-elevated px-4 py-10 text-center text-ink-muted">
            No batches yet. Load the synthetic supplier dataset to begin.
          </p>
        ) : (
          <ul className="space-y-3">
            {batches.map((b) => (
              <li key={b.id}>
                <Link
                  href={`/batches/${b.id}`}
                  className="block rounded border border-line bg-bg-elevated px-4 py-4 transition hover:border-charcoal/30"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="font-medium text-charcoal">{b.name}</div>
                      <div className="text-sm text-ink-muted">{b.supplier_name}</div>
                    </div>
                    <span className={`rounded px-2 py-1 text-xs font-medium ${statusColor(b.status)}`}>
                      {b.status}
                    </span>
                  </div>
                  <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-3 md:grid-cols-6">
                    {[
                      ["Imported", b.counts?.imported ?? 0],
                      ["Corrected", b.counts?.corrected ?? 0],
                      ["Awaiting", b.counts?.awaiting_decisions ?? b.counts?.pending_decisions ?? 0],
                      ["Published", b.counts?.published ?? 0],
                      ["Verified", b.counts?.verified ?? 0],
                      ["Failed", b.counts?.failed ?? 0],
                    ].map(([label, value]) => (
                      <div key={String(label)}>
                        <dt className="text-ink-muted">{label}</dt>
                        <dd className="text-lg font-medium tabular-nums">{value as number}</dd>
                      </div>
                    ))}
                  </dl>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
