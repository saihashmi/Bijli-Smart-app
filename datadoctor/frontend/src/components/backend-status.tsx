"use client";

import { useEffect, useState } from "react";

type Health = { status: string; version: string; ai_configured: boolean };
type State = { kind: "loading" } | { kind: "ok"; health: Health } | { kind: "error"; message: string };

/** Calls the real /api/health endpoint through the Next.js proxy. Nothing here is simulated. */
export function BackendStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetch("/api/health", { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return (await res.json()) as Health;
      })
      .then((health) => !cancelled && setState({ kind: "ok", health }))
      .catch((e: unknown) => !cancelled && setState({ kind: "error", message: e instanceof Error ? e.message : "unreachable" }));
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "loading") return <p data-testid="backend-status">Checking backend…</p>;
  if (state.kind === "error")
    return (
      <p data-testid="backend-status" className="text-destructive-text">
        Backend unreachable ({state.message}). Start it with <code>uvicorn app.main:app --port 8000</code>.
      </p>
    );
  return (
    <p data-testid="backend-status" className="text-success-text">
      Backend connected · API v{state.health.version} · AI {state.health.ai_configured ? "configured" : "not configured"}
    </p>
  );
}
