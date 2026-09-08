"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, Batch, Decision, Job, Product, statusColor } from "@/lib/api";

export default function BatchPage() {
  const params = useParams();
  const batchId = params.id as string;
  const [batch, setBatch] = useState<Batch | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [b, p, d, j] = await Promise.all([
        api.batch(batchId),
        api.products(batchId),
        api.decisions(batchId, "pending"),
        api.jobs(batchId),
      ]);
      setBatch(b);
      setProducts(p);
      setDecisions(d);
      setJobs(j);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load batch");
    }
  }, [batchId]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2500);
    return () => clearInterval(t);
  }, [refresh]);

  async function runProcess() {
    setBusy("process");
    try {
      await api.process(batchId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Process failed");
    } finally {
      setBusy(null);
    }
  }

  async function runPublish() {
    setBusy("publish");
    try {
      await api.publish(batchId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Publish failed");
    } finally {
      setBusy(null);
    }
  }

  if (!batch && !error) return <p className="text-ink-muted">Loading batch…</p>;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-ink-muted">
            <Link href="/" className="underline-offset-2 hover:underline">
              Batches
            </Link>{" "}
            / {batch?.name}
          </p>
          <h1 className="mt-1 text-3xl text-charcoal">{batch?.name}</h1>
          <p className="text-ink-muted">{batch?.supplier_name}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={runProcess}
            disabled={!!busy}
            className="rounded bg-charcoal px-3 py-2 text-sm text-bg-elevated disabled:opacity-50"
          >
            {busy === "process" ? "Queuing…" : "Run processing"}
          </button>
          <button
            type="button"
            onClick={runPublish}
            disabled={!!busy}
            className="rounded border border-line bg-bg-elevated px-3 py-2 text-sm disabled:opacity-50"
          >
            {busy === "publish" ? "Queuing…" : "Publish eligible"}
          </button>
          <Link
            href={`/batches/${batchId}/decisions`}
            className="rounded border border-amber/40 bg-amber-soft px-3 py-2 text-sm text-amber"
          >
            Decision inbox ({decisions.length})
          </Link>
          <Link
            href={`/batches/${batchId}/activity`}
            className="rounded border border-line px-3 py-2 text-sm"
          >
            Run activity
          </Link>
        </div>
      </div>

      {error && (
        <div className="rounded border border-red/30 bg-red-soft px-4 py-3 text-sm text-red" role="alert">
          {error}
        </div>
      )}

      {batch && (
        <dl className="grid grid-cols-2 gap-3 rounded border border-line bg-bg-elevated p-4 sm:grid-cols-3 md:grid-cols-6">
          {[
            ["Imported", batch.counts?.imported ?? 0],
            ["Corrected", batch.counts?.corrected ?? 0],
            ["Awaiting", batch.counts?.awaiting_decisions ?? batch.counts?.pending_decisions ?? 0],
            ["Published", batch.counts?.published ?? 0],
            ["Verified", batch.counts?.verified ?? 0],
            ["Failed", batch.counts?.failed ?? 0],
          ].map(([label, value]) => (
            <div key={String(label)}>
              <dt className="text-xs uppercase tracking-wide text-ink-muted">{label}</dt>
              <dd className="text-2xl font-medium tabular-nums">{value as number}</dd>
            </div>
          ))}
        </dl>
      )}

      <section>
        <h2 className="mb-3 text-xl">Products</h2>
        <div className="overflow-x-auto rounded border border-line bg-bg-elevated">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-line text-ink-muted">
              <tr>
                <th className="px-3 py-2 font-medium">SKU</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Verified</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id} className="border-b border-line/70 last:border-0">
                  <td className="px-3 py-2">
                    <Link href={`/products/${p.id}`} className="font-medium underline-offset-2 hover:underline">
                      {p.sku}
                    </Link>
                  </td>
                  <td className="px-3 py-2">
                    <span className={`rounded px-2 py-0.5 text-xs ${statusColor(p.status)}`}>{p.status}</span>
                  </td>
                  <td className="px-3 py-2">{p.verification_passed ? "Yes" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-xl">Jobs</h2>
        <ul className="space-y-2 text-sm">
          {jobs.map((j) => (
            <li key={j.id} className="rounded border border-line bg-bg-elevated px-3 py-2">
              <span className={`mr-2 rounded px-2 py-0.5 text-xs ${statusColor(j.status)}`}>{j.status}</span>
              {j.job_type} · mode {j.agent_mode}
              {j.error && <div className="mt-1 text-red">{j.error}</div>}
            </li>
          ))}
          {jobs.length === 0 && <li className="text-ink-muted">No jobs yet.</li>}
        </ul>
      </section>
    </div>
  );
}
