"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorState } from "@/components/RequestState";
import { ProductDetail, api, statusColor } from "@/lib/api";
import { fieldLabel } from "@/lib/field-labels";

const STEP_LABELS: Record<string, string> = {
  image_not_supplied: "Image not supplied",
  looking_up_manufacturer: "Looking up manufacturer record",
  matching_model: "Matching model",
  downloading_image: "Downloading image",
  image_ready_for_review: "Image ready for review",
  image_accepted: "Image accepted",
};

function Value({ value }: { value: unknown }) {
  if (value == null || value === "") return <span className="text-ink-muted">Empty</span>;
  if (Array.isArray(value)) return <span>{value.join(", ")}</span>;
  if (typeof value === "object") return <span>{JSON.stringify(value)}</span>;
  return <span>{String(value)}</span>;
}

export default function ProductPage() {
  const params = useParams();
  const id = params.id as string;
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .product(id)
      .then(setProduct)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }, [id]);

  if (error) return <ErrorState message={error} />;
  if (!product) return <p className="text-ink-muted">Loading product…</p>;

  const recovery = (product.provenance?.manufacturer_recovery || {}) as {
    steps?: Array<{ id: string; occurred?: boolean; status?: string }>;
    retrieval_mode?: string;
  };
  const steps = (recovery.steps || []).filter((s) => s.occurred !== false);
  const originalMissingImage = !product.original?.image_filename && !(product.original as { images?: unknown })?.images;

  return (
    <div className="space-y-8">
      <div>
        <p className="text-sm text-ink-muted">Product workbench</p>
        <h1 className="text-3xl text-charcoal">{String(product.proposed?.title || product.sku)}</h1>
        <p className="text-sm text-ink-muted">{product.sku}</p>
        <span className={`mt-2 inline-block rounded px-2 py-1 text-xs ${statusColor(product.status)}`}>
          {product.status}
        </span>
      </div>

      {steps.length > 0 && (
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {steps.map((step, index) => (
            <li key={`${step.id}-${index}`} className="rounded border border-line bg-bg-elevated p-3 text-sm">
              <div className="font-medium">{STEP_LABELS[step.id] || step.id.replace(/_/g, " ")}</div>
              {step.status && <div className="text-xs text-ink-muted">{step.status.replace(/_/g, " ")}</div>}
            </li>
          ))}
        </ol>
      )}
      {recovery.retrieval_mode && (
        <p className="text-xs text-ink-muted">Manufacturer retrieval mode: {recovery.retrieval_mode}</p>
      )}

      <section className="grid gap-6 md:grid-cols-2">
        <div className="rounded border border-line bg-bg-elevated p-4">
          <h2 className="mb-3 text-lg">Original supplier record</h2>
          {originalMissingImage && (
            <p className="mb-3 rounded border border-line bg-bg px-3 py-2 text-sm">No product photo was supplied.</p>
          )}
          <dl className="space-y-2 text-sm">
            {Object.entries(product.original || {}).map(([k, v]) => (
              <div key={k}>
                <dt className="text-ink-muted">{fieldLabel(k)}</dt>
                <dd className="font-medium">
                  <Value value={v} />
                </dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="rounded border border-line bg-bg-elevated p-4">
          <h2 className="mb-3 text-lg">Proposed listing</h2>
          {product.images.filter((img) => img.suitability !== "model_mismatch").map((img) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={img.id}
              src={api.mediaUrl(img.path)}
              alt={String(product.proposed?.title || "Proposed product photo")}
              className="mb-3 aspect-square w-full bg-bg object-contain"
            />
          ))}
          <dl className="space-y-2 text-sm">
            {["title", "brand", "manufacturer_reference", "collection", "caliber", "movement_type", "case_diameter", "water_resistance"].map(
              (k) => (
                <div key={k}>
                  <dt className="text-ink-muted">{fieldLabel(k)}</dt>
                  <dd className="font-medium">
                    <Value value={product.proposed?.[k]} />
                  </dd>
                </div>
              ),
            )}
          </dl>
        </div>
      </section>

      <section className="rounded border border-line bg-bg-elevated p-4">
        <h2 className="mb-3 text-lg">Images</h2>
        <ul className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
          {product.images.map((img) => (
            <li key={img.id} className="rounded border border-line p-3 text-sm">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={api.mediaUrl(img.path)} alt={img.class} className="mb-2 aspect-square w-full bg-bg object-contain" />
              <div>
                {img.class} {img.is_primary ? "(primary)" : ""}
              </div>
              <div className="text-xs text-ink-muted">
                {img.source_kind} · {img.usage_permission} · {img.suitability}
              </div>
              {img.match_rationale && <p className="mt-1 text-xs text-ink-muted">{img.match_rationale}</p>}
            </li>
          ))}
          {product.images.length === 0 && <li className="text-ink-muted">No images assigned</li>}
        </ul>
      </section>

      {product.store_product_id && product.store_slug && (
        <Link href={`/store/products/${product.store_slug}`} className="inline-block text-green underline">
          View demo storefront
        </Link>
      )}
    </div>
  );
}
