"use client";

// Remembers the last opened analysis session in this browser (a convenience only; the server is the source of truth).
const KEY = "dd:last-session";

export function rememberSession(id: string) {
  try {
    localStorage.setItem(KEY, id);
  } catch {
    /* storage unavailable: ignore */
  }
}

export function lastSession(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function forgetSession(id?: string) {
  try {
    if (!id || localStorage.getItem(KEY) === id) localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

/** Session id from a /s/<id>/... path. */
export function sessionIdFromPath(pathname: string): string | null {
  const m = /^\/s\/([0-9a-f-]{36})(?:\/|$)/.exec(pathname);
  return m ? m[1] : null;
}
