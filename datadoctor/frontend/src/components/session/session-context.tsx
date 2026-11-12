"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import Link from "next/link";
import { FolderOpen, RotateCw } from "lucide-react";
import { api, ApiError, type AnalysisSession } from "@/lib/api";
import { forgetSession, rememberSession } from "@/lib/last-session";
import { setCurrentSession } from "@/lib/session-store";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { SessionHeader } from "./session-header";

type Ctx = { session: AnalysisSession; reload: () => void; setSession: (s: AnalysisSession) => void };
const SessionCtx = createContext<Ctx | null>(null);

export function useAnalysisSession(): Ctx {
  const ctx = useContext(SessionCtx);
  if (!ctx) throw new Error("useAnalysisSession must be used inside SessionProvider");
  return ctx;
}

export function SessionProvider({ sessionId, children }: { sessionId: string; children: React.ReactNode }) {
  const [session, setSession] = useState<AnalysisSession | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const reload = useCallback(() => {
    setError(null);
    api
      .session(sessionId)
      .then((s) => {
        setSession(s);
        rememberSession(s.id);
      })
      .catch((e: unknown) => {
        const err = e instanceof ApiError ? e : new ApiError(0, "UNKNOWN", "Could not load this analysis session.");
        if (err.status === 404) forgetSession(sessionId);
        setError(err);
      });
  }, [sessionId]);
  useEffect(reload, [reload]);
  useEffect(() => {
    setCurrentSession(session);
    return () => setCurrentSession(null);
  }, [session]);

  if (error)
    return (
      <Alert variant={error.status === 404 ? "warning" : "destructive"} data-testid="session-error">
        <FolderOpen aria-hidden />
        <AlertTitle>{error.status === 404 ? "This analysis session is not available" : "Could not load the session"}</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>
            {error.status === 404
              ? "It may have been deleted, expired after the retention period, or belong to another browser."
              : error.message}
          </p>
          <div className="flex gap-2">
            <Button asChild size="sm">
              <Link href="/workspace">Go to Workspace</Link>
            </Button>
            {error.status !== 404 && (
              <Button variant="outline" size="sm" onClick={reload}>
                <RotateCw /> Try again
              </Button>
            )}
          </div>
        </AlertDescription>
      </Alert>
    );

  if (!session)
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading session">
        <Skeleton className="h-16 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );

  return (
    <SessionCtx.Provider value={{ session, reload, setSession }}>
      <SessionHeader session={session} />
      {children}
    </SessionCtx.Provider>
  );
}
