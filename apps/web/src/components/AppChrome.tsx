"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ModeInfo } from "@/lib/api";
import { CART_EVENT, shopperCount } from "@/lib/shopper-cart";

function isOperatorPath(pathname: string): boolean {
  return (
    pathname.startsWith("/workspace") ||
    pathname.startsWith("/batches") ||
    pathname.startsWith("/import") ||
    pathname.startsWith("/products/")
  );
}

export function ModeBadge() {
  const [mode, setMode] = useState<ModeInfo | null>(null);
  useEffect(() => {
    api.mode().then(setMode).catch(() => setMode(null));
  }, []);
  if (!mode) return null;
  const mixed = mode.is_live && mode.lookup_is_replay;
  return (
    <span
      className={`inline-flex min-h-11 items-center rounded px-3 py-2 text-sm font-medium ${
        mode.is_replay || mixed ? "bg-amber-soft text-amber" : "bg-green-soft text-green"
      }`}
      title={
        mode.is_replay
          ? "Deterministic fixture path through the same services — not a live model."
          : mixed
            ? "Live Strands/Bedrock with replay lookup fixtures — not a live catalog lookup."
            : "Strands agent with Amazon Bedrock and live lookup."
      }
    >
      {mode.label}
    </span>
  );
}

function CartLink() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const refresh = () => {
      api
        .cart()
        .then((cart) => setCount(shopperCount(cart.items)))
        .catch(() => setCount(0));
    };
    refresh();
    window.addEventListener(CART_EVENT, refresh);
    return () => window.removeEventListener(CART_EVENT, refresh);
  }, []);
  return (
    <Link
      href="/store/cart"
      className="inline-flex min-h-11 items-center rounded border border-line px-3 py-2 text-sm font-medium text-ink hover:bg-bg"
    >
      Cart{" "}
      <span className="ml-1 tabular-nums" aria-live="polite">
        ({count})
      </span>
    </Link>
  );
}

export function AppNav() {
  const pathname = usePathname() || "/";
  const operator = isOperatorPath(pathname);
  const linkClass =
    "inline-flex min-h-11 items-center px-2 text-sm font-medium text-ink hover:text-charcoal";

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-bg-elevated/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-2 md:px-6">
        <div className="flex flex-wrap items-center gap-1 sm:gap-2">
          <Link
            href="/"
            className="inline-flex min-h-11 items-center font-[family-name:var(--font-display)] text-xl text-charcoal"
          >
            ShelfReady
          </Link>
          <nav className="flex flex-wrap items-center" aria-label="Primary">
            <Link href="/store" className={linkClass}>
              Shop
            </Link>
            {operator ? (
              <>
                <Link href="/workspace" className={linkClass}>
                  Batches
                </Link>
                <Link href="/import" className={linkClass}>
                  Import
                </Link>
              </>
            ) : (
              <Link href="/workspace" className={linkClass}>
                Operator workspace
              </Link>
            )}
          </nav>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <CartLink />
          {operator && <ModeBadge />}
        </div>
      </div>
    </header>
  );
}
