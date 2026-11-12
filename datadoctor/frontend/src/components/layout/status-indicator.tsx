"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { Loader2 } from "lucide-react";
import { activity } from "@/lib/api";

/** Real processing status: shows "Working" while API requests are in flight (after a short delay to avoid flicker). */
export function StatusIndicator() {
  const count = useSyncExternalStore(activity.subscribe, activity.get, () => 0);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (count === 0) {
      setBusy(false);
      return;
    }
    const t = setTimeout(() => setBusy(true), 250);
    return () => clearTimeout(t);
  }, [count]);

  return (
    <span
      role="status"
      aria-live="polite"
      data-testid="status-indicator"
      data-busy={busy}
      className="hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium text-muted-foreground sm:inline-flex"
    >
      {busy ? (
        <>
          <Loader2 className="size-3 animate-spin text-cyan-text" aria-hidden /> Working…
        </>
      ) : (
        <>
          <span className="size-1.5 rounded-full bg-success" aria-hidden /> Ready
        </>
      )}
    </span>
  );
}
