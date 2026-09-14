"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export function AccessPanel({ onUnlocked }: { onUnlocked?: () => void }) {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.unlock(token);
      onUnlocked?.();
    } catch {
      setError("That operator token was not accepted.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto max-w-lg rounded border border-line bg-bg-elevated px-5 py-8">
      <h1 className="text-3xl text-charcoal">Operator workspace</h1>
      <p className="mt-3 text-ink-muted">
        Importing catalogs, editing products, and publishing listings requires operator access. The
        public demo store stays available without a token.
      </p>
      <form className="mt-6 space-y-3" onSubmit={submit}>
        <label className="block text-sm font-medium text-ink" htmlFor="operator-token">
          Operator access token
        </label>
        <input
          id="operator-token"
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          autoComplete="current-password"
          className="min-h-11 w-full rounded border border-charcoal/30 bg-bg px-3 py-2 text-base text-ink"
        />
        {error && (
          <p className="text-sm text-red" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={busy || !token}
          className="min-h-11 rounded bg-charcoal px-4 text-sm font-medium text-bg-elevated disabled:opacity-50"
        >
          {busy ? "Checking…" : "Continue to workspace"}
        </button>
      </form>
    </section>
  );
}
