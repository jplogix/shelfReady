"use client";

import Link from "next/link";
import { Batch, ModeInfo } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";

type Props = {
  batch: Batch;
  mode?: ModeInfo | null;
  primaryAction?: { label: string; onClick: () => void; disabled?: boolean };
  secondaryActions?: React.ReactNode;
};

export function BatchHeader({ batch, mode, primaryAction, secondaryActions }: Props) {
  const imported = new Date(batch.created_at).toLocaleString();

  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <p className="text-sm text-ink-muted">
          <Link href="/" className="underline-offset-2 hover:underline">
            Batches
          </Link>{" "}
          / {batch.name}
        </p>
        <h1 className="mt-1 text-3xl text-charcoal">{batch.name}</h1>
        <p className="text-ink-muted">
          {batch.supplier_name} · imported {imported}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <StatusBadge status={batch.status} />
          {mode && (
            <span className="rounded border border-line bg-bg-elevated px-2 py-0.5 text-xs text-ink-muted">
              {mode.label}
            </span>
          )}
          {batch.source_filename && (
            <span className="text-xs text-ink-muted">{batch.source_filename}</span>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {primaryAction && (
          <button
            type="button"
            onClick={primaryAction.onClick}
            disabled={primaryAction.disabled}
            className="rounded bg-charcoal px-4 py-2.5 text-sm font-medium text-bg-elevated disabled:opacity-50"
          >
            {primaryAction.label}
          </button>
        )}
        {secondaryActions}
      </div>
    </div>
  );
}
