"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { BatchHeader } from "@/components/BatchHeader";
import { BatchSummary } from "@/components/BatchSummary";
import { ProductDrawer } from "@/components/ProductDrawer";
import { ProductTable } from "@/components/ProductTable";
import { api, Batch, Job, ModeInfo, Product, ProductDetail } from "@/lib/api";
import { statusColor } from "@/lib/api";

type Filter = "all" | "ready_to_publish" | "needs_information" | "has_conflicts" | "published";

export default function BatchPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const batchId = params.id as string;

  const [batch, setBatch] = useState<Batch | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [mode, setMode] = useState<ModeInfo | null>(null);
  const [drawerProduct, setDrawerProduct] = useState<ProductDetail | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [b, p, j, m] = await Promise.all([
        api.batch(batchId),
        api.products(batchId, {
          readiness: filter === "all" ? undefined : filter,
          search: search || undefined,
        }),
        api.jobs(batchId),
        api.mode(),
      ]);
      setBatch(b);
      setProducts(p);
      setJobs(j);
      setMode(m);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load batch");
    }
  }, [batchId, filter, search]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2500);
    return () => clearInterval(t);
  }, [refresh]);

  const openProductId = searchParams.get("product");

  useEffect(() => {
    if (openProductId) {
      api.product(openProductId).then(setDrawerProduct).catch(() => setDrawerProduct(null));
    } else {
      setDrawerProduct(null);
    }
  }, [openProductId]);

  function openProduct(id: string) {
    router.push(`/batches/${batchId}?product=${id}`, { scroll: false });
  }

  function closeDrawer() {
    router.push(`/batches/${batchId}`, { scroll: false });
  }

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
      const ids = Array.from(selected);
      if (!ids.length) {
        setError("Select at least one ready product to publish.");
        return;
      }
      await api.publish(batchId, ids);
      setSelected(new Set());
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Publish failed");
    } finally {
      setBusy(null);
    }
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const primaryAction = useMemo(() => {
    if (!batch) return undefined;
    const ready = batch.counts?.ready_to_publish ?? 0;
    const published = batch.counts?.published ?? 0;
    if (batch.status === "draft" || batch.status === "ready") {
      return { label: busy === "process" ? "Queuing…" : "Prepare products", onClick: runProcess, disabled: !!busy };
    }
    if (ready > 0) {
      return {
        label: busy === "publish" ? "Publishing…" : `Review and publish (${selected.size || ready})`,
        onClick: runPublish,
        disabled: !!busy,
      };
    }
    if (published > 0) {
      return { label: "View published products", onClick: () => setFilter("published"), disabled: false };
    }
    return { label: "Run processing", onClick: runProcess, disabled: !!busy };
  }, [batch, busy, selected.size]);

  if (!batch && !error) return <p className="text-ink-muted">Loading batch…</p>;

  return (
    <div className="mx-auto max-w-[1400px] space-y-8">
      <BatchHeader
        batch={batch!}
        mode={mode}
        primaryAction={primaryAction}
        secondaryActions={
          <>
            <Link href={`/batches/${batchId}/activity`} className="rounded border border-line px-3 py-2 text-sm">
              Run activity
            </Link>
          </>
        }
      />

      {error && (
        <div className="rounded border border-red/30 bg-red-soft px-4 py-3 text-sm text-red" role="alert">
          {error}
        </div>
      )}

      {batch && <BatchSummary batch={batch} />}

      <ProductTable
        products={products}
        filter={filter}
        onFilterChange={setFilter}
        search={search}
        onSearchChange={setSearch}
        selected={selected}
        onToggleSelect={toggleSelect}
        onOpenProduct={openProduct}
      />

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

      {drawerProduct && (
        <ProductDrawer
          product={drawerProduct}
          onClose={closeDrawer}
          onRefresh={async () => {
            await refresh();
            if (openProductId) setDrawerProduct(await api.product(openProductId));
          }}
        />
      )}
    </div>
  );
}
