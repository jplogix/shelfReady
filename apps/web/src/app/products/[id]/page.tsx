"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ProductDetail, api, statusColor } from "@/lib/api";

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

  if (error) return <p className="text-red">{error}</p>;
  if (!product) return <p className="text-ink-muted">Loading product…</p>;

  return (
    <div className="space-y-8">
      <div>
        <p className="text-sm text-ink-muted">Product workbench</p>
        <h1 className="text-3xl text-charcoal">{product.sku}</h1>
        <span className={`mt-2 inline-block rounded px-2 py-1 text-xs ${statusColor(product.status)}`}>
          {product.status}
        </span>
      </div>

      <section className="grid gap-6 md:grid-cols-2">
        <div className="rounded border border-line bg-bg-elevated p-4">
          <h2 className="mb-3 text-lg">Original (supplier)</h2>
          <pre className="max-h-96 overflow-auto text-xs text-ink-muted">
            {JSON.stringify(product.original, null, 2)}
          </pre>
        </div>
        <div className="rounded border border-line bg-bg-elevated p-4">
          <h2 className="mb-3 text-lg">Proposed</h2>
          <pre className="max-h-96 overflow-auto text-xs text-ink-muted">
            {JSON.stringify(product.proposed, null, 2)}
          </pre>
        </div>
      </section>

      <section className="rounded border border-line bg-bg-elevated p-4">
        <h2 className="mb-3 text-lg">Field differences</h2>
        {product.diffs?.length ? (
          <ul className="space-y-2 text-sm">
            {product.diffs.map((d) => (
              <li key={d.field} className="grid gap-1 sm:grid-cols-3">
                <span className="font-medium">{d.field}</span>
                <span className="text-ink-muted line-through">{String(d.original ?? "")}</span>
                <span>{String(d.proposed ?? "")}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-ink-muted">No field diffs yet.</p>
        )}
      </section>

      <section className="rounded border border-line bg-bg-elevated p-4">
        <h2 className="mb-3 text-lg">Images</h2>
        <ul className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
          {product.images.map((img) => (
            <li key={img.id} className="rounded border border-line p-3 text-sm">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={api.mediaUrl(img.path)}
                alt={img.class}
                className="mb-2 aspect-square w-full object-cover"
              />
              <div>
                {img.class} {img.is_primary ? "(primary)" : ""}
              </div>
              <div className="text-xs text-ink-muted">{img.classification_source}</div>
            </li>
          ))}
          {product.images.length === 0 && <li className="text-ink-muted">No images</li>}
        </ul>
      </section>

      <section className="rounded border border-line bg-bg-elevated p-4">
        <h2 className="mb-2 text-lg">SEO preview</h2>
        <p className="mb-3 text-xs text-amber">Demo storefront is explicitly noindex — preview only.</p>
        <dl className="space-y-2 text-sm">
          {Object.entries(product.seo || {}).map(([k, v]) => (
            <div key={k}>
              <dt className="text-ink-muted">{k}</dt>
              <dd>{String(v)}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="rounded border border-line bg-bg-elevated p-4">
        <h2 className="mb-2 text-lg">Provenance</h2>
        <pre className="text-xs text-ink-muted">{JSON.stringify(product.provenance, null, 2)}</pre>
        <h3 className="mt-4 text-base">Blockers</h3>
        <pre className="text-xs text-ink-muted">{JSON.stringify(product.blockers, null, 2)}</pre>
      </section>

      {product.store_product_id && (
        <Link href="/store" className="inline-block text-green underline">
          View demo storefront
        </Link>
      )}
    </div>
  );
}
