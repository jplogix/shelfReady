"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, Decision } from "@/lib/api";

export default function DecisionsPage() {
  const params = useParams();
  const batchId = params.id as string;
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Record<string, string>>({});

  const refresh = useCallback(async () => {
    try {
      setDecisions(await api.decisions(batchId, "pending"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load decisions");
    }
  }, [batchId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function resolve(id: string, action: string, edited?: string) {
    try {
      await api.resolveDecision(id, {
        action,
        edited_value: edited,
        save_as_rule: action === "edit" && !!edited,
        rule_type: action === "edit" ? "brand" : undefined,
        rule_target: edited,
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Resolve failed");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-ink-muted">
          <Link href={`/batches/${batchId}`} className="hover:underline">
            Batch
          </Link>{" "}
          / Decision inbox
        </p>
        <h1 className="text-3xl text-charcoal">Decision inbox</h1>
        <p className="text-ink-muted">
          Ambiguous or consequential changes pause here. Approvals bind to the reviewed product version.
        </p>
      </div>

      {error && (
        <div className="rounded border border-red/30 bg-red-soft px-4 py-3 text-sm text-red" role="alert">
          {error}
        </div>
      )}

      {decisions.length === 0 ? (
        <p className="rounded border border-dashed border-line bg-bg-elevated px-4 py-10 text-center text-ink-muted">
          No pending decisions. Eligible products can be published.
        </p>
      ) : (
        <ul className="space-y-4">
          {decisions.map((d) => (
            <li key={d.id} className="rounded border border-amber/30 bg-bg-elevated p-4">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded bg-amber-soft px-2 py-0.5 text-amber">{d.kind}</span>
                <span className="rounded bg-line px-2 py-0.5 text-ink-muted">{d.risk_tier}</span>
                {d.field_name && <span className="text-ink-muted">field: {d.field_name}</span>}
              </div>
              <p className="mt-2 font-medium text-charcoal">{d.reason}</p>
              <p className="mt-1 text-sm text-ink-muted">{d.consequence}</p>
              <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-ink-muted">Original</dt>
                  <dd className="font-mono text-xs break-all">{JSON.stringify(d.original_value)}</dd>
                </div>
                <div>
                  <dt className="text-ink-muted">Proposed</dt>
                  <dd className="font-mono text-xs break-all">{JSON.stringify(d.proposed_value)}</dd>
                </div>
              </dl>
              {(d.kind === "unknown_brand_alias" ||
                d.kind === "ambiguous_category" ||
                d.kind === "missing_price" ||
                d.kind === "unknown_color_alias") && (
                <label className="mt-3 block text-sm">
                  Edit value
                  <input
                    className="mt-1 w-full rounded border border-line bg-bg px-3 py-2"
                    value={editValues[d.id] || ""}
                    onChange={(e) => setEditValues((s) => ({ ...s, [d.id]: e.target.value }))}
                    aria-label={`Edit value for ${d.kind}`}
                  />
                </label>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  className="rounded bg-green px-3 py-1.5 text-sm text-white"
                  onClick={() => resolve(d.id, "approve")}
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="rounded border border-line px-3 py-1.5 text-sm"
                  onClick={() => resolve(d.id, "edit", editValues[d.id])}
                  disabled={!editValues[d.id]}
                >
                  Save edit
                </button>
                <button
                  type="button"
                  className="rounded border border-red/30 px-3 py-1.5 text-sm text-red"
                  onClick={() => resolve(d.id, "reject")}
                >
                  Reject
                </button>
                {d.product_id && (
                  <Link href={`/products/${d.product_id}`} className="px-3 py-1.5 text-sm underline">
                    Open product
                  </Link>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
