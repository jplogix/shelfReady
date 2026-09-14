"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AgentAction, Job, api } from "@/lib/api";

export default function ActivityPage() {
  const params = useParams();
  const batchId = params.id as string;
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [actions, setActions] = useState<AgentAction[]>([]);

  useEffect(() => {
    api.jobs(batchId).then((j) => {
      setJobs(j);
      if (j[0]) setSelected(j[0].id);
    });
  }, [batchId]);

  useEffect(() => {
    if (!selected) return;
    api.actions(selected).then(setActions);
    const t = setInterval(() => api.actions(selected).then(setActions), 2000);
    return () => clearInterval(t);
  }, [selected]);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-ink-muted">
          <Link href={`/batches/${batchId}`} className="hover:underline">
            Batch
          </Link>{" "}
          / Run activity
        </p>
        <h1 className="text-3xl text-charcoal">Run activity</h1>
        <p className="text-ink-muted">Persisted tool actions and results — not a simulated chat transcript.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {jobs.map((j) => (
          <button
            key={j.id}
            type="button"
            onClick={() => setSelected(j.id)}
            className={`rounded border px-3 py-1.5 text-sm ${
              selected === j.id ? "border-charcoal bg-charcoal text-bg-elevated" : "border-line bg-bg-elevated"
            }`}
          >
            {j.job_type} · {j.status}
          </button>
        ))}
      </div>

      <ol className="space-y-3">
        {actions.map((a) => (
          <li key={a.id} className="rounded border border-line bg-bg-elevated p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-charcoal">{a.tool_name}</span>
              <span className={a.success ? "text-green" : "text-red"}>
                {a.success ? "ok" : "failed"}
              </span>
              {typeof a.output_payload?.duration_ms === "number" && (
                <span className="text-xs text-ink-muted">{a.output_payload.duration_ms}ms</span>
              )}
              {typeof a.input_payload?.product_id === "string" && a.input_payload.product_id && (
                <span className="text-xs text-ink-muted">product {a.input_payload.product_id.slice(0, 8)}</span>
              )}
              {a.evidence_summary && <span className="text-ink-muted">{a.evidence_summary}</span>}
            </div>
            <pre className="mt-2 max-h-40 overflow-auto rounded bg-bg p-2 text-xs text-ink-muted">
              {JSON.stringify({ input: a.input_payload, output: a.output_payload }, null, 2)}
            </pre>
          </li>
        ))}
        {actions.length === 0 && <li className="text-ink-muted">No tool actions recorded for this job yet.</li>}
      </ol>
    </div>
  );
}
