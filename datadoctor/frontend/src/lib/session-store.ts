"use client";

import { useSyncExternalStore } from "react";
import type { AnalysisSession } from "./api";

// The analysis session currently open, shared with the top bar and command palette.
let current: AnalysisSession | null = null;
const listeners = new Set<() => void>();

export function setCurrentSession(s: AnalysisSession | null) {
  current = s;
  listeners.forEach((l) => l());
}

export function useCurrentSession(): AnalysisSession | null {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => current,
    () => null,
  );
}
