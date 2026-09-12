"use client";

import { Product, api } from "@/lib/api";
import { ReadinessBadge } from "./StatusBadge";

type Filter = "all" | "ready_to_publish" | "needs_information" | "has_conflicts" | "published";

type Props = {
  products: Product[];
  filter: Filter;
  onFilterChange: (f: Filter) => void;
  search: string;
  onSearchChange: (s: string) => void;
  selected: Set<string>;
  onToggleSelect: (id: string) => void;
  onOpenProduct: (id: string) => void;
};

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "ready_to_publish", label: "Ready" },
  { id: "needs_information", label: "Needs information" },
  { id: "has_conflicts", label: "Conflicts" },
  { id: "published", label: "Published" },
];

export function ProductTable({
  products,
  filter,
  onFilterChange,
  search,
  onSearchChange,
  selected,
  onToggleSelect,
  onOpenProduct,
}: Props) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl">Products</h2>
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => onFilterChange(f.id)}
              className={`rounded px-3 py-1.5 text-sm ${
                filter === f.id ? "bg-charcoal text-bg-elevated" : "border border-line bg-bg-elevated"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>
      <input
        type="search"
        placeholder="Search name, SKU, barcode…"
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        className="w-full max-w-md rounded border border-line bg-bg-elevated px-3 py-2 text-sm"
      />
      <div className="overflow-x-auto rounded border border-line bg-bg-elevated">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-line text-ink-muted">
            <tr>
              <th className="px-3 py-2 font-medium"> </th>
              <th className="px-3 py-2 font-medium">Product</th>
              <th className="px-3 py-2 font-medium">Price</th>
              <th className="px-3 py-2 font-medium">Readiness</th>
              <th className="px-3 py-2 font-medium">Enrichment</th>
              <th className="px-3 py-2 font-medium">Next action</th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr
                key={p.id}
                className="border-b border-line/70 last:border-0 hover:bg-bg/50"
              >
                <td className="px-3 py-2">
                  {p.readiness === "ready_to_publish" && (
                    <input
                      type="checkbox"
                      checked={selected.has(p.id)}
                      onChange={() => onToggleSelect(p.id)}
                      aria-label={`Select ${p.title || p.sku}`}
                    />
                  )}
                </td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    onClick={() => onOpenProduct(p.id)}
                    className="flex items-center gap-3 text-left"
                  >
                    {p.thumbnail ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={api.mediaUrl(p.thumbnail)}
                        alt=""
                        className="h-12 w-12 rounded object-cover"
                      />
                    ) : (
                      <div className="flex h-12 w-12 items-center justify-center rounded bg-line text-xs text-ink-muted">
                        No img
                      </div>
                    )}
                    <div>
                      <div className="font-medium text-charcoal">{p.title || p.supplier_sku || p.sku}</div>
                      <div className="text-xs text-ink-muted">SKU {p.supplier_sku || p.sku.split("__row")[0]}</div>
                    </div>
                  </button>
                </td>
                <td className="px-3 py-2 tabular-nums">
                  {p.price ? `${p.currency || "USD"} ${p.price}` : "—"}
                </td>
                <td className="px-3 py-2">
                  <ReadinessBadge readiness={p.readiness} />
                  {(p.issue_count ?? 0) > 0 && (
                    <span className="ml-1 text-xs text-amber">{p.issue_count} issues</span>
                  )}
                </td>
                <td className="px-3 py-2 text-xs text-ink-muted">{p.enrichment_summary || "—"}</td>
                <td className="px-3 py-2 text-xs">{p.next_action || "—"}</td>
              </tr>
            ))}
            {products.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-ink-muted">
                  No products match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
