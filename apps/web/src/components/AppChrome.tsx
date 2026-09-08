"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ModeInfo } from "@/lib/api";

export function ModeBadge() {
  const [mode, setMode] = useState<ModeInfo | null>(null);
  useEffect(() => {
    api.mode().then(setMode).catch(() => setMode(null));
  }, []);
  if (!mode) return null;
  return (
    <span
      className={`inline-flex items-center rounded px-2.5 py-1 text-xs font-medium tracking-wide ${
        mode.is_replay ? "bg-amber-soft text-amber" : "bg-green-soft text-green"
      }`}
      title={
        mode.is_replay
          ? "Deterministic fixture path through the same services — not a live model."
          : "Strands agent with Amazon Bedrock."
      }
    >
      {mode.label}
    </span>
  );
}

export function AppNav() {
  return (
    <header className="border-b border-line bg-bg-elevated/90 backdrop-blur sticky top-0 z-20">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 md:px-6">
        <div className="flex items-center gap-6">
          <Link href="/" className="font-[family-name:var(--font-display)] text-xl text-charcoal">
            ShelfReady
          </Link>
          <nav className="hidden items-center gap-4 text-sm text-ink-muted sm:flex">
            <Link href="/" className="hover:text-ink">
              Batches
            </Link>
            <Link href="/import" className="hover:text-ink">
              Import
            </Link>
            <Link href="/store" className="hover:text-ink">
              Demo store
            </Link>
          </nav>
        </div>
        <ModeBadge />
      </div>
    </header>
  );
}
