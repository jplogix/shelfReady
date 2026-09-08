"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Cart = {
  id: string;
  items: Array<{
    id: string;
    title?: string;
    quantity: number;
    unit_price: string;
    currency: string;
  }>;
};

export default function CartPage() {
  const [cart, setCart] = useState<Cart | null>(null);

  useEffect(() => {
    api.cart().then(setCart);
  }, []);

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
      </div>
      {!cart || cart.items.length === 0 ? (
        <p className="text-ink-muted">Cart is empty.</p>
      ) : (
        <ul className="space-y-3">
          {cart.items.map((item) => (
            <li key={item.id} className="flex justify-between rounded border border-line bg-bg-elevated px-4 py-3">
              <div>
                <div className="font-medium">{item.title || item.id}</div>
                <div className="text-sm text-ink-muted">Qty {item.quantity}</div>
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
