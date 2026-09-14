"use client";

import { useEffect, useState } from "react";
import { AccessPanel } from "@/components/AccessPanel";
import { api } from "@/lib/api";

export function OperatorGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<"loading" | "needed" | "ok">("loading");

  useEffect(() => {
    api
      .session()
      .then((s) => setState(s.authenticated ? "ok" : "needed"))
      .catch(() => setState("needed"));
  }, []);

  if (state === "loading") {
    return <p className="text-ink-muted">Checking operator access…</p>;
  }
  if (state === "needed") {
    return <AccessPanel onUnlocked={() => window.location.reload()} />;
  }
  return <>{children}</>;
}
