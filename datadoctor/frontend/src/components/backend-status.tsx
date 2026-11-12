"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, Loader2 } from "lucide-react";
import { api, ApiError, type ServerHealth } from "@/lib/api";

type State = { kind: "loading" } | { kind: "ok"; health: ServerHealth } | { kind: "error"; message: string };

/** Live check against /api/health. Nothing here is simulated. */
export function BackendStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((health) => !cancelled && setState({ kind: "ok", health }))
      .catch((e: unknown) => {
        if (!cancelled) setState({ kind: "error", message: e instanceof ApiError ? e.message : "Unreachable" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "loading")
    return (
      <p data-testid="backend-status" className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Checking server…
      </p>
    );
  if (state.kind === "error")
    return (
      <p data-testid="backend-status" className="flex items-center gap-2 text-destructive-text">
        <CircleAlert className="size-4 shrink-0" aria-hidden /> Server unreachable: {state.message}
      </p>
    );
  const { health } = state;
  return (
    <div data-testid="backend-status" className="space-y-1.5">
      <p className="flex items-center gap-2 text-success-text">
        <CheckCircle2 className="size-4" aria-hidden /> Backend connected · API v{health.version}
      </p>
      <p className="text-muted-foreground">
        Database: {health.checks.database === "ok" ? "OK" : "error"} · Storage: {health.checks.storage === "ok" ? "OK" : "error"}
      </p>
    </div>
  );
}
