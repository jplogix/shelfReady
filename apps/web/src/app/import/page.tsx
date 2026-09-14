"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function ImportPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [headers, setHeaders] = useState<string[]>([]);
  const [preview, setPreview] = useState<Record<string, string>[]>([]);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<"upload" | "map">("upload");

  async function createAndUpload() {
    if (!file) return;
    setError(null);
    try {
      const created = await api.createBatch(file.name, "Uploaded supplier");
      const body = await api.uploadCsv(created.id, file);
      setBatchId(created.id);
      setMapping(body.mapping);
      setHeaders(body.headers);
      setPreview(body.preview_rows);
      setStep("map");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    }
  }

  async function commit() {
    if (!batchId) return;
    try {
      await api.importBatch(batchId, mapping);
      router.push(`/batches/${batchId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl text-charcoal">Import wizard</h1>
        <p className="text-ink-muted">Upload CSV, map columns, preview rows, then begin processing.</p>
      </div>

      {error && (
        <div className="rounded border border-red/30 bg-red-soft px-4 py-3 text-sm text-red" role="alert">
          {error}
        </div>
      )}

      {step === "upload" && (
        <div className="space-y-4 rounded border border-line bg-bg-elevated p-4">
          <label className="block text-sm">
            CSV file
            <input
              type="file"
              accept=".csv,text/csv"
              className="mt-2 block w-full text-sm"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </label>
          <button
            type="button"
            disabled={!file}
            onClick={createAndUpload}
            className="rounded bg-charcoal px-4 py-2 text-sm text-bg-elevated disabled:opacity-50"
          >
            Upload & preview
          </button>
          <p className="text-sm text-ink-muted">
            Or{" "}
            <button
              type="button"
              className="underline"
              onClick={() => api.loadSample().then((b) => router.push(`/batches/${b.id}`))}
            >
              load the bundled sample catalog
            </button>
            .
          </p>
        </div>
      )}

      {step === "map" && (
        <div className="space-y-4">
          <h2 className="text-xl">Column mapping</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.keys(mapping).map((field) => (
              <label key={field} className="text-sm">
                {field}
                <select
                  className="mt-1 w-full rounded border border-line bg-bg px-2 py-2"
                  value={mapping[field] || ""}
                  onChange={(e) => setMapping((m) => ({ ...m, [field]: e.target.value || null }))}
                >
                  <option value="">—</option>
                  {headers.map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <h2 className="text-xl">Preview</h2>
          <pre className="max-h-64 overflow-auto rounded border border-line bg-bg-elevated p-3 text-xs">
            {JSON.stringify(preview, null, 2)}
          </pre>
          <button type="button" onClick={commit} className="rounded bg-green px-4 py-2 text-sm text-white">
            Validate & import
          </button>
        </div>
      )}
    </div>
  );
}
