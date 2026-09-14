"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState } from "@/components/RequestState";
import { ShopperItem, getShopperCart, shopperCount } from "@/lib/shopper-cart";

export default function CartPage() {
  const [items, setItems] = useState<ShopperItem[] | null>(null);

  useEffect(() => {
    setItems(getShopperCart());
  }, []);

  if (items === null) return <p className="text-ink-muted">Loading cart…</p>;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-ink-muted">
          <Link href="/store" className="hover:underline">
            Store
          </Link>{" "}
          / Cart
        </p>
        <h1 className="text-3xl text-charcoal">Cart</h1>
        <p className="text-ink-muted">Demo cart only — no payment or checkout.</p>
        <p className="sr-only" aria-live="polite">
          Cart has {shopperCount(items)} items
        </p>
      </div>
      {items.length === 0 ? (
        <EmptyState>Cart is empty.</EmptyState>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.store_product_id} className="flex justify-between rounded border border-line bg-bg-elevated px-4 py-3">
              <div>
                <Link href={`/store/products/${item.slug}`} className="font-medium underline">
                  {item.title}
                </Link>
                <div className="text-sm text-ink-muted">Qty {item.quantity}</div>
              </div>
              <div className="tabular-nums">
                {item.currency} {item.price}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
