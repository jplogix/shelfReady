"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, Batch } from "@/lib/api";
import { statusColor } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [batches, setBatches] = useState<Batch[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [showDev, setShowDev] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const all = await api.batches();
      setBatches(showDev ? all : all.filter((b) => b.batch_kind !== "import" || b.name.includes("Demo") || b.name.includes("Stress")));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load batches");
    } finally {
      setLoading(false);
    }
  }, [showDev]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function loadDemo() {
    setBusy("demo");
    try {
      const batch = await api.loadDemo();
      router.push(`/batches/${batch.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Demo load failed");
    } finally {
      setBusy(null);
    }
  }

  async function loadSample() {
    setBusy("sample");
    try {
      const batch = await api.loadSample();
      router.push(`/batches/${batch.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sample load failed");
    } finally {
      setBusy(null);
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
          Import a catalog, inspect evidence-backed corrections, resolve exceptions in a product workspace,
          publish to the demo store, and verify purchasability.
        </p>
        <div className="flex flex-wrap gap-3 pt-2">
          <button
            type="button"
            onClick={loadDemo}
            disabled={!!busy}
            className="rounded bg-charcoal px-4 py-2.5 text-sm font-medium text-bg-elevated disabled:opacity-60"
          >
            {busy === "demo" ? "Loading…" : "Try demo catalog"}
          </button>
          <Link
            href="/import"
            className="rounded border border-line bg-bg-elevated px-4 py-2.5 text-sm font-medium"
          >
            Import supplier CSV
          </Link>
          <button
            type="button"
            onClick={() => setShowDev(!showDev)}
            className="rounded border border-line px-4 py-2.5 text-sm text-ink-muted"
          >
            {showDev ? "Hide" : "Show"} dev batches
          </button>
        </div>
        {showDev && (
          <button
            type="button"
            onClick={loadSample}
            disabled={!!busy}
            className="text-sm text-ink-muted underline disabled:opacity-60"
          >
            {busy === "sample" ? "Loading…" : "Load stress-test catalog"}
          </button>
        )}
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
        <h2 className="mb-3 text-xl">Recent batches</h2>
        {loading ? (
          <p className="text-ink-muted">Loading…</p>
        ) : batches.length === 0 ? (
          <p className="text-ink-muted">No batches yet. Try the demo catalog to get started.</p>
        ) : (
          <ul className="divide-y divide-line rounded border border-line bg-bg-elevated">
            {batches.map((b) => (
              <li key={b.id}>
                <Link
                  href={`/batches/${b.id}`}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 hover:bg-bg/60"
                >
                  <div>
                    <div className="font-medium text-charcoal">{b.name}</div>
                    <div className="text-sm text-ink-muted">
                      {b.supplier_name} · {new Date(b.created_at).toLocaleString()}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <span className={`rounded px-2 py-0.5 text-xs ${statusColor(b.status)}`}>{b.status}</span>
                    <span className="text-ink-muted">
                      {b.counts?.published ?? 0} published · {b.counts?.ready_to_publish ?? 0} ready
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
