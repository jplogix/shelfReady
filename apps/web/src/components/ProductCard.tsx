import Link from "next/link";
import { StoreProduct, api } from "@/lib/api";

export function ProductCard({ product, priority = false }: { product: StoreProduct; priority?: boolean }) {
  return (
    <li>
      <Link
        href={`/store/products/${product.slug}`}
        className="block overflow-hidden rounded border border-line bg-bg-elevated focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green"
      >
        {product.primary_image_path ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={api.mediaUrl(product.primary_image_path)}
            alt={product.images.find((img) => img.is_primary)?.alt || product.title}
            className="aspect-square w-full object-cover"
            loading={priority ? "eager" : "lazy"}
          />
        ) : (
          <div className="flex aspect-square items-center justify-center bg-line text-sm text-ink-muted">
            No image
          </div>
        )}
        <div className="space-y-1 p-4">
          <div className="text-xs uppercase tracking-wide text-ink-muted">{product.brand}</div>
          <div className="font-medium text-charcoal">{product.title}</div>
          <div className="tabular-nums text-ink">
            {product.currency} {product.price}
          </div>
          <div className="text-sm text-ink-muted">{product.available ? "In stock" : "Out of stock"}</div>
        </div>
      </Link>
    </li>
  );
}

export function ProductGrid({ products }: { products: StoreProduct[] }) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {products.map((product, index) => (
        <ProductCard key={product.id} product={product} priority={index < 2} />
      ))}
    </ul>
  );
}
