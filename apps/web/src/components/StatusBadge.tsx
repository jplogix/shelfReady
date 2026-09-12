import { readinessLabel, statusColor } from "@/lib/api";

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${statusColor(status)}`}>{status.replace(/_/g, " ")}</span>
  );
}

export function ReadinessBadge({ readiness }: { readiness?: string | null }) {
  if (!readiness) return null;
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${statusColor(readiness)}`}>
      {readinessLabel(readiness)}
    </span>
  );
}
