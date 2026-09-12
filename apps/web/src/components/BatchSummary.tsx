import { Batch } from "@/lib/api";

export function BatchSummary({ batch }: { batch: Batch }) {
  const c = batch.counts || {};
  const items = [
    ["Ready to publish", c.ready_to_publish ?? 0],
    ["Needs information", c.needs_information ?? 0],
    ["Has conflicts", c.has_conflicts ?? 0],
    ["Published", c.published ?? 0],
    ["Verified", c.verified ?? 0],
    ["Verify failed", c.verification_failed ?? 0],
  ];

  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-2 gap-3 rounded border border-line bg-bg-elevated p-4 sm:grid-cols-3 lg:grid-cols-6">
        {items.map(([label, value]) => (
          <div key={String(label)}>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">{label}</dt>
            <dd className="text-2xl font-medium tabular-nums">{value as number}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap gap-4 text-sm text-ink-muted">
        <span>{c.source_rows ?? c.products ?? 0} source rows → {c.products ?? 0} products</span>
        {(c.issues ?? 0) > 0 && (
          <span className="text-amber">
            {c.issues} issues across {c.products_with_issues ?? 0} products
          </span>
        )}
        {(c.fields_corrected ?? 0) > 0 && (
          <span>{c.fields_corrected} fields updated across batch</span>
        )}
      </div>
    </div>
  );
}
