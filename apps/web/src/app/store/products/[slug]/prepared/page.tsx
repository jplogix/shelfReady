"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorState } from "@/components/RequestState";
import { ListingProvenance, api } from "@/lib/api";
import { fieldLabel } from "@/lib/field-labels";

function Value({ value }: { value: unknown }) {
  if (value == null || value === "") return <span className="text-ink-muted">Empty</span>;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <span>{String(value)}</span>;
  }
  return <span>{JSON.stringify(value)}</span>;
}

export default function PreparedListingPage() {
  const params = useParams();
  const slug = params.slug as string;
  const [data, setData] = useState<ListingProvenance | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listingProvenance(slug)
      .then((body) => {
        setData(body);
        setError(null);
      })
      .catch((e) => {
        setData(null);
        setError(e instanceof Error ? e.message : "Could not load preparation details.");
      });
  }, [slug]);

  if (error) {
    return <ErrorState title="Preparation details unavailable" message={error} />;
  }
  if (!data) return <p className="text-ink-muted">Loading how this listing was prepared…</p>;

  const originalFields = data.original_fields?.length
    ? data.original_fields
    : Object.entries(data.original_row).map(([field, value]) => ({
        field,
        label: fieldLabel(field),
        value,
      }));

  return (
    <div className="space-y-8">
      <div>
        <p className="text-sm text-ink-muted">
          <Link href={`/store/products/${data.slug}`} className="underline">
            {data.title}
          </Link>{" "}
          / How this listing was prepared
        </p>
        <h1 className="mt-2 text-3xl text-charcoal">See how this listing was prepared</h1>
        <p className="mt-2 max-w-2xl text-ink-muted">
          Read-only view of the original supplier row, accepted corrections, and supporting evidence.
          Import, editing, and publication stay in the operator workspace.
        </p>
        <p className="mt-2 text-sm text-ink-muted">
          Prepared with <span className="font-medium text-ink">{data.preparation_label}</span>
          {data.agent_mode === "replay"
            ? ". Replay uses the same validation and publish path without a live model call. Structured Strands assessments appear when live agent mode is enabled."
            : ". Live Strands structured output was persisted for this listing."}
        </p>
        {data.outcome_summary && <p className="mt-3 text-lg text-charcoal">{data.outcome_summary}</p>}
        {data.image_caption && (
          <p className="mt-2 text-sm text-ink-muted">
            Listing image: {data.image_caption}
            {data.image_suitability === "source_model_match"
              ? " Source/model association was checked against the manufacturer page."
              : ""}
            {data.image_suitability === "category_mismatch"
              ? " The file loaded, but it is not a category-matching product image."
              : ""}
          </p>
        )}
      </div>

      {data.assessment && (
        <section className="rounded border border-line bg-bg-elevated p-4">
          <h2 className="text-xl">Agent assessment</h2>
          <p className="mt-2 text-sm text-ink-muted">
            {data.assessment.match_outcome.replace(/_/g, " ")} · {data.assessment.explanation}
          </p>
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="rounded border border-line bg-bg-elevated p-4">
          <h2 className="text-xl">Original supplier row</h2>
          {originalFields.length === 0 ? (
            <p className="mt-3 text-sm text-ink-muted">No original fields were retained.</p>
          ) : (
            <dl className="mt-3 space-y-2 text-sm">
              {originalFields.map((row) => (
                <div key={row.field}>
                  <dt className="text-ink-muted">{row.label}</dt>
                  <dd className="font-medium">
                    <Value value={row.value} />
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </section>

        <section className="rounded border border-line bg-bg-elevated p-4">
          <h2 className="text-xl">Accepted corrections</h2>
          {data.corrections.length === 0 ? (
            <p className="mt-3 text-sm text-ink-muted">
              The published listing matches the supplier row on retained fields.
            </p>
          ) : (
            <ul className="mt-3 space-y-3 text-sm">
              {data.corrections.map((row) => (
                <li key={row.field} className="border-b border-line pb-3 last:border-0">
                  <div className="font-medium">{row.label}</div>
                  <div className="text-ink-muted">
                    From <Value value={row.original} /> → <Value value={row.accepted} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded border border-line bg-bg-elevated p-4">
          <h2 className="text-xl">Supporting evidence</h2>
          {data.evidence.length === 0 ? (
            <p className="mt-3 text-sm text-ink-muted">No lookup evidence was attached to this listing.</p>
          ) : (
            <ul className="mt-3 space-y-3 text-sm">
              {data.evidence.map((row, index) => (
                <li key={`${row.field_name}-${index}`} className="border-b border-line pb-3 last:border-0">
                  <div className="font-medium">{row.label}</div>
                  <p>{row.match_explanation}</p>
                  <p className="text-ink-muted">
                    {row.source_provider}
                    {row.is_replay ? " · replay fixture" : " · live lookup"} · {row.match_outcome.replace(/_/g, " ")}
                  </p>
                  {(row.original_supplier_value != null && row.original_supplier_value !== "") ||
                  row.proposed_value != null ? (
                    <p className="text-ink-muted">
                      Supplier <Value value={row.original_supplier_value} /> → evidence{" "}
                      <Value value={row.proposed_value} />
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
