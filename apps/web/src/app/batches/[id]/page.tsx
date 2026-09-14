"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { BatchHeader } from "@/components/BatchHeader";
import { BatchSummary } from "@/components/BatchSummary";
import { ProductDrawer } from "@/components/ProductDrawer";
import { ProductTable } from "@/components/ProductTable";
import { ErrorState } from "@/components/RequestState";
import { api, Batch, Decision, DemoFixResult, Job, ModeInfo, Product, ProductDetail } from "@/lib/api";
import { statusColor } from "@/lib/api";

type Filter = "all" | "ready_to_publish" | "needs_information" | "has_conflicts" | "published";

function isRecommendedDemoDecision(decision: Decision): boolean {
  if (["accept_enrichment", "unsupported_claim", "unknown_brand_alias"].includes(decision.kind)) {
    return decision.proposed_value != null;
  }
  if (decision.kind === "no_primary_image") return decision.proposed_value != null;
  if (decision.kind === "conflicting_variant") {
    return decision.field_name !== "primary_image" && decision.proposed_value != null;
  }
  return ["unknown_color_alias", "ambiguous_category"].includes(decision.kind)
    && (decision.proposed_value != null || decision.original_value != null);
}

export default function BatchPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const batchId = params.id as string;

  const [batch, setBatch] = useState<Batch | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [mode, setMode] = useState<ModeInfo | null>(null);
  const [drawerProduct, setDrawerProduct] = useState<ProductDetail | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [fixResult, setFixResult] = useState<DemoFixResult | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [b, p, j, m, d] = await Promise.all([
        api.batch(batchId),
        api.products(batchId, {
          readiness: filter === "all" ? undefined : filter,
          search: search || undefined,
        }),
        api.jobs(batchId),
        api.mode(),
        api.decisions(batchId),
      ]);
      setBatch(b);
      setProducts(p);
      setJobs(j);
      setMode(m);
      setDecisions(d);
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
      let ids = Array.from(selected);
      if (!ids.length) {
        ids = (await api.products(batchId, { readiness: "ready_to_publish" })).map((product) => product.id);
      }
      if (!ids.length) {
        setError("There are no ready products to publish yet.");
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

  async function applyRecommendedFixes() {
    setBusy("fixes");
    setError(null);
    try {
      const result = await api.applyRecommendedDemoFixes(batchId);
      setFixResult(result);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not apply recommended fixes");
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

  const primaryAction = (() => {
    if (!batch) return undefined;
    const ready = batch.counts?.ready_to_publish ?? 0;
    const published = batch.counts?.published ?? 0;
    const isSeikoDemo = batch.batch_kind === "demo" && batch.source_filename === "seiko_demo_catalog.csv";
    const hasRecommendedFixes = decisions.some(isRecommendedDemoDecision);
    if (batch.status === "draft" || batch.status === "ready") {
      return { label: busy === "process" ? "Queuing…" : "Prepare products", onClick: runProcess, disabled: !!busy };
    }
    if (batch.status === "processing") {
      return { label: "Preparing products…", onClick: runProcess, disabled: true };
    }
    if (ready > 0) {
      return {
        label: busy === "publish" ? "Publishing…" : `Review and publish (${selected.size || ready})`,
        onClick: runPublish,
        disabled: !!busy,
      };
    }
    if (isSeikoDemo && hasRecommendedFixes) {
      return {
        label: busy === "fixes" ? "Applying fixes…" : "Apply recommended fixes",
        onClick: applyRecommendedFixes,
        disabled: !!busy,
      };
    }
    if (published > 0) {
      return { label: "View published products", onClick: () => setFilter("published"), disabled: false };
    }
    return { label: "Run processing", onClick: runProcess, disabled: !!busy };
  })();

  if (!batch && error) {
    return <ErrorState message={error} onRetry={refresh} />;
  }
  if (!batch) return <p className="text-ink-muted">Loading batch…</p>;

  const isSeikoDemo = batch.batch_kind === "demo" && batch.source_filename === "seiko_demo_catalog.csv";
  const hasRecommendedFixes = decisions.some(isRecommendedDemoDecision);
  const pendingIssues = batch.counts?.issues ?? decisions.length;
  const firstReviewProductId = decisions.find((decision) => decision.product_id)?.product_id;

  return (
    <div className="mx-auto max-w-[1400px] space-y-8">
      <BatchHeader
        batch={batch}
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

      {error && <ErrorState message={error} onRetry={refresh} />}

      {batch && <BatchSummary batch={batch} />}

      {isSeikoDemo && batch.status === "awaiting_decisions" && (
        <section className="rounded border border-green/30 bg-green-soft p-4" aria-live="polite">
          <h2 className="text-lg text-charcoal">Preparation found changes to review</h2>
          {fixResult ? (
            <p className="mt-1 text-sm text-ink-muted">
              Applied {fixResult.resolved} evidence-backed fixes. {fixResult.ready_to_publish} products are
              ready to publish; {fixResult.remaining} decisions across {fixResult.remaining_products} products
              still need a person to review the identity or image.
            </p>
          ) : hasRecommendedFixes ? (
            <p className="mt-1 text-sm text-ink-muted">
              Apply the manufacturer-backed specifications, recovered hero image, and verified variant
              correction in one step. ShelfReady will leave the ambiguous reference and wrong-variant image
              unresolved for manual review.
            </p>
          ) : (
            <p className="mt-1 text-sm text-ink-muted">
              The evidence-backed fixes are applied. {batch.counts?.ready_to_publish ?? 0} products are ready
              to publish; {batch.counts?.issues ?? 0} decisions across {batch.counts?.products_with_issues ?? 0}
              products still need a person to review the identity or image.
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {pendingIssues > 0 && firstReviewProductId && (
              <Link href={`/batches/${batchId}?product=${firstReviewProductId}&review=1`} className="rounded border border-line bg-bg-elevated px-4 py-2 text-sm">
                Review {pendingIssues} remaining {pendingIssues === 1 ? "issue" : "issues"}
              </Link>
            )}
          </div>
        </section>
      )}

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
          initialTab={searchParams.get("review") === "1" ? "evidence" : "supplier"}
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
