"use client";

import { useState } from "react";
import Link from "next/link";
import { Decision, ProductDetail, api } from "@/lib/api";
import { ReadinessBadge, StatusBadge } from "./StatusBadge";

function DecisionActions({
  decision,
  onResolved,
}: {
  decision: Decision;
  onResolved: () => void;
}) {
  const [editValue, setEditValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const needsEdit =
    decision.kind === "missing_price" ||
    decision.kind === "unknown_brand_alias" ||
    decision.kind === "unknown_color_alias" ||
    decision.kind === "ambiguous_category";

  const canApprove =
    decision.proposed_value != null &&
    decision.kind !== "missing_price" &&
    !["unknown_brand_alias", "unknown_color_alias", "ambiguous_category"].includes(decision.kind);

  async function resolve(action: string, edited_value?: unknown) {
    setBusy(true);
    setError(null);
    try {
      await api.resolveDecision(decision.id, { action, edited_value });
      onResolved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  const isImage =
    decision.field_name === "primary_image" && typeof decision.evidence?.preview_path === "string";
  const preview = isImage ? String(decision.evidence.preview_path) : null;

  return (
    <div className="rounded border border-line bg-bg p-3 text-sm">
      <div className="mb-1 flex flex-wrap gap-2">
        <span className="rounded bg-line px-2 py-0.5 text-xs">{decision.kind.replace(/_/g, " ")}</span>
        <span className="text-xs text-ink-muted">{decision.risk_tier}</span>
      </div>
      {preview && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={api.mediaUrl(preview)} alt="Retrieved product photograph" className="mb-2 aspect-square max-h-48 w-full object-contain bg-bg" />
      )}
      {isImage && (
        <dl className="mb-2 grid gap-1 text-xs text-ink-muted">
          <div>Model: {String(decision.evidence.manufacturer_reference || "")}</div>
          {typeof decision.evidence.source_page === "string" && (
            <div>
              Source:{" "}
              <a className="underline" href={decision.evidence.source_page} target="_blank" rel="noreferrer">
                manufacturer page
              </a>
            </div>
          )}
          <div>Retrieved: {String(decision.evidence.retrieved_at || "")}</div>
          <div>Match: {String(decision.evidence.match_rationale || "")}</div>
          <div>
            Usage: {String(decision.evidence.usage_permission || "")} · suitability{" "}
            {String(decision.evidence.suitability || "")}
          </div>
        </dl>
      )}
      <p className="font-medium">{decision.reason}</p>
      <p className="text-xs text-ink-muted">{decision.consequence}</p>
      {needsEdit && (
        <input
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          placeholder={
            decision.kind === "missing_price"
              ? "Enter price"
              : decision.kind === "ambiguous_category"
                ? "Enter category"
                : "Enter value"
          }
          className="mt-2 w-full rounded border border-line px-2 py-1.5 text-sm"
        />
      )}
      <div className="mt-2 flex flex-wrap gap-2">
        {canApprove && (
          <button
            type="button"
            disabled={busy}
            onClick={() => resolve("approve")}
            className="rounded bg-green px-2 py-1 text-xs text-white disabled:opacity-50"
          >
            Accept {isImage ? "image" : "correction"}
          </button>
        )}
        {needsEdit && (
          <button
            type="button"
            disabled={busy || !editValue}
            onClick={() => resolve("edit", editValue)}
            className="rounded bg-charcoal px-2 py-1 text-xs text-bg-elevated disabled:opacity-50"
          >
            Save edit
          </button>
        )}
        {!needsEdit && !canApprove && decision.kind !== "accept_enrichment" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => resolve("approve")}
            className="rounded border border-line px-2 py-1 text-xs disabled:opacity-50"
          >
            Approve
          </button>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={() => resolve("reject")}
          className="rounded border border-red/30 px-2 py-1 text-xs text-red disabled:opacity-50"
        >
          Reject
        </button>
      </div>
      {error && <p className="mt-1 text-xs text-red">{error}</p>}
    </div>
  );
}

type Tab = "supplier" | "evidence" | "preview";

export function ProductDrawer({
  product,
  onClose,
  onRefresh,
}: {
  product: ProductDetail;
  onClose: () => void;
  onRefresh: () => void;
}) {
  const [tab, setTab] = useState<Tab>("supplier");
  const [showDev, setShowDev] = useState(false);

  const tabs: { id: Tab; label: string }[] = [
    { id: "supplier", label: "Supplier record" },
    { id: "evidence", label: "Evidence & decisions" },
    { id: "preview", label: "Storefront preview" },
  ];

  return (
    <dialog open className="fixed inset-0 z-50 m-0 h-full w-full max-w-none border-0 bg-black/40 p-0 backdrop:bg-black/40">
      <div className="ml-auto flex h-full w-full max-w-3xl flex-col bg-bg-elevated shadow-xl lg:max-w-[720px]">
        <header className="flex items-start justify-between border-b border-line px-6 py-4">
          <div>
            <p className="text-sm text-ink-muted">Product workspace</p>
            <h2 className="text-2xl text-charcoal">{product.title || product.supplier_sku || product.sku}</h2>
            <div className="mt-1 flex gap-2">
              <ReadinessBadge readiness={product.readiness} />
              <StatusBadge status={product.status} />
            </div>
          </div>
          <button type="button" onClick={onClose} className="rounded border border-line px-3 py-1.5 text-sm">
            Close
          </button>
        </header>

        <div className="flex border-b border-line px-6">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`border-b-2 px-3 py-2 text-sm ${
                tab === t.id ? "border-charcoal text-charcoal" : "border-transparent text-ink-muted"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {tab === "supplier" && (
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              {Object.entries(product.original || {}).map(([k, v]) => (
                <div key={k}>
                  <dt className="text-ink-muted">{k}</dt>
                  <dd className="font-medium">{v != null ? String(v) : "—"}</dd>
                </div>
              ))}
              {product.import_row_number && (
                <div className="sm:col-span-2 text-xs text-ink-muted">
                  Source row #{product.import_row_number}
                  {product.sku.includes("__row") && ` · internal id ${product.sku}`}
                </div>
              )}
            </dl>
          )}

          {tab === "evidence" && (
            <div className="space-y-4">
              {(product.field_evidence || []).map((ev) => (
                <div key={ev.id} className="rounded border border-line p-3 text-sm">
                  <div className="flex flex-wrap gap-2 text-xs text-ink-muted">
                    <span>{ev.field_name}</span>
                    <span>{ev.match_outcome.replace(/_/g, " ")}</span>
                    <span>{ev.source_provider}</span>
                    {ev.is_replay && <span className="text-amber">replay fixture</span>}
                    {ev.is_cached && <span>cached</span>}
                  </div>
                  <p className="mt-1">{ev.match_explanation}</p>
                </div>
              ))}
              {(product.decisions || []).map((d) => (
                <DecisionActions key={d.id} decision={d} onResolved={onRefresh} />
              ))}
              {!product.field_evidence?.length && !product.decisions?.length && (
                <p className="text-ink-muted">No open evidence or decisions.</p>
              )}
              <button type="button" className="text-xs underline" onClick={() => setShowDev(!showDev)}>
                {showDev ? "Hide" : "Show"} developer details
              </button>
              {showDev && (
                <pre className="max-h-48 overflow-auto rounded bg-bg p-2 text-xs">
                  {JSON.stringify({ diffs: product.diffs, provenance: product.provenance }, null, 2)}
                </pre>
              )}
            </div>
          )}

          {tab === "preview" && (
            <div className="space-y-4">
              <div className="rounded border border-line p-4">
                {product.images?.[0] && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={api.mediaUrl(product.images.find((i) => i.is_primary)?.path || product.images[0].path)}
                    alt=""
                    className="mb-3 aspect-square max-h-48 object-contain"
                  />
                )}
                <h3 className="text-xl text-charcoal">
                  {String(
                    (product.seo as Record<string, string>)?.product_title ||
                      product.proposed?.title ||
                      product.title ||
                      "",
                  )}
                </h3>
                <p className="text-lg tabular-nums">
                  {String(product.proposed?.currency || "USD")}{" "}
                  {String(product.proposed?.price || product.price || "—")}
                </p>
                <p className="mt-2 text-sm text-ink-muted">
                  {String(product.proposed?.description || product.original?.description || "")}
                </p>
                {product.store_slug && (
                  <Link
                    href={`/store/products/${product.store_slug}`}
                    className="mt-3 inline-block text-sm text-green underline"
                  >
                    View in demo store →
                  </Link>
                )}
              </div>
              <div className="rounded border border-amber/30 bg-amber-soft/30 p-3 text-xs text-ink-muted">
                <p className="font-medium text-amber">SEO preview (noindex demo)</p>
                <p className="mt-1">{(product.seo as Record<string, string>)?.meta_title}</p>
                <p>{(product.seo as Record<string, string>)?.meta_description}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </dialog>
  );
}
