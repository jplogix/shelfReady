"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorState } from "@/components/RequestState";
import { api, Batch, statusColor } from "@/lib/api";

export default function WorkspacePage() {
  const router = useRouter();
  const [batches, setBatches] = useState<Batch[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [showDev, setShowDev] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const all = await api.batches();
      setBatches(
        showDev
          ? all
          : all.filter((b) => b.batch_kind !== "import" || b.name.includes("Demo") || b.name.includes("Stress")),
      );
      setError(null);
    } catch (e) {
      setBatches(null);
      setError(e instanceof Error ? e.message : "Could not load batches.");
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
        <p className="text-sm uppercase tracking-[0.14em] text-ink-muted">Operator workspace</p>
        <h1 className="max-w-2xl text-4xl text-charcoal md:text-5xl">Prepare and publish catalogs</h1>
        <p className="max-w-xl text-lg text-ink-muted">
          Import a catalog, inspect evidence-backed corrections, resolve exceptions, then publish.
          Shoppers see only approved listings in the demo store.
        </p>
        <div className="flex flex-wrap gap-3 pt-2">
          <button
            type="button"
            onClick={loadDemo}
            disabled={!!busy}
            className="min-h-11 rounded bg-charcoal px-4 text-sm font-medium text-bg-elevated disabled:opacity-60"
          >
            {busy === "demo" ? "Loading…" : "Try demo catalog"}
          </button>
          <Link
            href="/import"
            className="inline-flex min-h-11 items-center rounded border border-line bg-bg-elevated px-4 text-sm font-medium"
          >
            Import supplier CSV
          </Link>
          <button
            type="button"
            onClick={() => setShowDev(!showDev)}
            className="min-h-11 rounded border border-line px-4 text-sm text-ink"
          >
            {showDev ? "Hide" : "Show"} dev batches
          </button>
        </div>
        {showDev && (
          <button
            type="button"
            onClick={loadSample}
            disabled={!!busy}
            className="min-h-11 text-sm text-ink underline disabled:opacity-60"
          >
            {busy === "sample" ? "Loading…" : "Load stress-test catalog"}
          </button>
        )}
      </section>

      {error && <ErrorState message={error} onRetry={refresh} />}

      <section>
        <h2 className="mb-3 text-xl">Recent batches</h2>
        {error ? null : batches === null ? (
          <p className="text-ink-muted">Loading batches…</p>
        ) : batches.length === 0 ? (
          <EmptyState>No batches yet. Try the demo catalog to get started.</EmptyState>
        ) : (
          <ul className="divide-y divide-line rounded border border-line bg-bg-elevated">
            {batches.map((b) => (
              <li key={b.id}>
                <Link
                  href={`/batches/${b.id}`}
                  className="flex min-h-11 flex-wrap items-center justify-between gap-3 px-4 py-3 hover:bg-bg/60"
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
