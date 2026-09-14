"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState, ErrorState } from "@/components/RequestState";
import type { ShopperCart } from "@/lib/api";
import { api } from "@/lib/api";
import { shopperCount } from "@/lib/shopper-cart";

export default function CartPage() {
  const [cart, setCart] = useState<ShopperCart | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .cart()
      .then((body) => {
        setCart(body);
        setError(null);
      })
      .catch((e) => {
        setCart(null);
        setError(e instanceof Error ? e.message : "Could not load the cart.");
      });
  }, []);

  if (error) {
    return <ErrorState title="Cart unavailable" message={error} />;
  }
  if (cart === null) return <p className="text-ink-muted">Loading cart…</p>;

  const items = cart.items;
  const count = shopperCount(items);

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
        <p className="text-ink-muted">Demo cart only — no payment or checkout. Prices and stock are checked on the server.</p>
        <p className="sr-only" aria-live="polite">
          Cart has {count} items
        </p>
      </div>
      {items.length === 0 ? (
        <EmptyState>Cart is empty.</EmptyState>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.store_product_id} className="flex justify-between rounded border border-line bg-bg-elevated px-4 py-3">
              <div>
                {item.slug ? (
                  <Link href={`/store/products/${item.slug}`} className="font-medium underline">
                    {item.title}
                  </Link>
                ) : (
                  <span className="font-medium">{item.title}</span>
                )}
                <div className="text-sm text-ink-muted">
                  Qty {item.quantity}
                  {item.stock ? ` · ${item.stock} available` : ""}
                </div>
              </div>
              <div className="tabular-nums">
                {item.currency} {item.unit_price}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
