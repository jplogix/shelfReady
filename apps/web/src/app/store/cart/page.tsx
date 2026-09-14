"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState, ErrorState } from "@/components/RequestState";
import type { ShopperCart } from "@/lib/api";
import { api } from "@/lib/api";
import { notifyCartChanged, shopperCount } from "@/lib/shopper-cart";

export default function CartPage() {
  const [cart, setCart] = useState<ShopperCart | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function refresh() {
    try {
      const body = await api.cart();
      setCart(body);
      setError(null);
      notifyCartChanged();
    } catch (e) {
      setCart(null);
      setError(e instanceof Error ? e.message : "Could not load the cart.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function updateQty(storeProductId: string, quantity: number) {
    setBusy(storeProductId);
    try {
      const body = await api.updateCartItem(storeProductId, quantity);
      setCart(body);
      notifyCartChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update quantity.");
    } finally {
      setBusy(null);
    }
  }

  async function remove(storeProductId: string) {
    setBusy(storeProductId);
    try {
      const body = await api.removeCartItem(storeProductId);
      setCart(body);
      notifyCartChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not remove this item.");
    } finally {
      setBusy(null);
    }
  }

  if (error && !cart) {
    return <ErrorState title="Cart unavailable" message={error} />;
  }
  if (cart === null) return <p className="text-ink-muted">Loading cart…</p>;

  const items = cart.items;
  const count = cart.item_count ?? shopperCount(items);
  const noun = count === 1 ? "item" : "items";

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
        <p className="text-ink-muted">Demo cart—no payment or checkout. Prices and stock are checked on the server.</p>
        <p className="sr-only" aria-live="polite">
          Cart has {count} {noun}
        </p>
      </div>
      {error && cart && (
        <p className="text-sm text-red" role="alert">
          {error}
        </p>
      )}
      {items.length === 0 ? (
        <EmptyState>
          Cart is empty.{" "}
          <Link href="/store" className="underline">
            Continue shopping
          </Link>
        </EmptyState>
      ) : (
        <>
          <ul className="space-y-3">
            {items.map((item) => (
              <li
                key={item.store_product_id}
                className="flex flex-col gap-3 rounded border border-line bg-bg-elevated px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex gap-3">
                  {item.image ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={api.mediaUrl(item.image)}
                      alt=""
                      className="h-16 w-16 rounded border border-line bg-bg object-contain"
                    />
                  ) : (
                    <div className="flex h-16 w-16 items-center justify-center rounded border border-line text-xs text-ink-muted">
                      No image
                    </div>
                  )}
                  <div>
                    {item.slug ? (
                      <Link href={`/store/products/${item.slug}`} className="font-medium underline">
                        {item.title}
                      </Link>
                    ) : (
                      <span className="font-medium">{item.title}</span>
                    )}
                    <div className="text-sm text-ink-muted">
                      {item.currency} {item.unit_price} each
                      {item.stock ? ` · ${item.stock} available` : ""}
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <label className="text-sm" htmlFor={`qty-${item.store_product_id}`}>
                        Quantity
                      </label>
                      <input
                        id={`qty-${item.store_product_id}`}
                        type="number"
                        min={1}
                        max={item.stock}
                        value={item.quantity}
                        disabled={busy === item.store_product_id}
                        onChange={(e) => updateQty(item.store_product_id, Number(e.target.value))}
                        className="w-16 rounded border border-line px-2 py-1 text-sm"
                      />
                      <button
                        type="button"
                        className="text-sm text-red underline"
                        disabled={busy === item.store_product_id}
                        onClick={() => remove(item.store_product_id)}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </div>
                <div className="tabular-nums font-medium">
                  {item.currency} {item.line_total ?? item.unit_price}
                </div>
              </li>
            ))}
          </ul>
          <p className="text-lg tabular-nums">
            Subtotal ({count} {noun}): {cart.currency || items[0]?.currency} {cart.subtotal}
          </p>
          <Link href="/store" className="inline-block text-sm underline">
            Continue shopping
          </Link>
        </>
      )}
    </div>
  );
}
