"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Copy, Gauge, Grid3x3, Info, Loader2, RotateCw, Rows3, Search, SquareDashed } from "lucide-react";
import { api, ApiError, type Profile } from "@/lib/api";
import { formatInteger } from "@/lib/format";
import { useAnalysisSession } from "@/components/session/session-context";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ColumnCard } from "./column-card";
import { DataGrid } from "./data-grid";

function Kpi({ icon: Icon, label, value, sub }: { icon: typeof Rows3; label: string; value: string; sub?: string }) {
  return (
    <Card className="gap-1 py-4">
      <CardContent className="px-4">
        <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Icon className="size-3.5" aria-hidden /> {label}
        </p>
        <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}

export function HealthView() {
  const { session } = useAnalysisSession();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const load = useCallback(() => {
    setError(null);
    setProfile(null);
    api
      .profile(session.id)
      .then(setProfile)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Could not profile the data."));
  }, [session.id]);
  useEffect(load, [load]);

  const columns = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = profile?.column_profiles ?? [];
    return q ? list.filter((c) => c.name.toLowerCase().includes(q) || c.type.includes(q)) : list;
  }, [profile, query]);

  return (
    <div className="space-y-6">
      {(session.warnings.length > 0 || session.header_changes.length > 0) && (
        <Alert variant="info">
          <Info aria-hidden />
          <AlertTitle>How the sheet was read</AlertTitle>
          <AlertDescription>
            <ul className="mt-1 list-disc space-y-0.5 pl-4">
              {session.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
              {session.header_changes.map((c) => (
                <li key={c.position}>
                  Column {c.position}:{" "}
                  {c.reason === "blank"
                    ? `blank header named “${c.new}”`
                    : c.reason === "duplicate"
                      ? `duplicate header “${c.original}” renamed “${c.new}”`
                      : `extra spaces removed from header “${c.new}”`}
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertTriangle aria-hidden />
          <AlertTitle>Profiling failed</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>{error}</p>
            <Button variant="outline" size="sm" onClick={load}>
              <RotateCw /> Try again
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {!profile && !error && (
        <div className="space-y-4" aria-busy="true">
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Profiling {formatInteger(session.rows ?? 0)} rows × {formatInteger(session.columns ?? 0)} columns…
          </p>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
        </div>
      )}

      {profile && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="health-kpis">
            <Kpi icon={Rows3} label="Rows" value={formatInteger(profile.rows)} sub={`${formatInteger(profile.columns)} columns`} />
            <Kpi
              icon={SquareDashed}
              label="Missing cells"
              value={`${profile.missing_pct}%`}
              sub={`${formatInteger(profile.missing_cells)} of ${formatInteger(profile.total_cells)}`}
            />
            <Kpi
              icon={Copy}
              label="Exact duplicate rows"
              value={formatInteger(profile.duplicate_rows)}
              sub={
                profile.empty_rows
                  ? `${formatInteger(profile.empty_rows)} completely empty row${profile.empty_rows === 1 ? "" : "s"}`
                  : "No empty rows"
              }
            />
            <Card className="gap-1 border-dashed py-4">
              <CardContent className="px-4">
                <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                  <Gauge className="size-3.5" aria-hidden /> Data Health Score
                </p>
                <p className="mt-1 text-sm">
                  Calculated in <Badge variant="warning">Milestone 6</Badge>
                </p>
                <p className="text-xs text-muted-foreground">Together with the issue list and fixes.</p>
              </CardContent>
            </Card>
          </div>

          <Tabs defaultValue="columns">
            <TabsList>
              <TabsTrigger value="columns">
                <Grid3x3 aria-hidden /> Column profiles
              </TabsTrigger>
              <TabsTrigger value="preview">
                <Rows3 aria-hidden /> Data preview
              </TabsTrigger>
            </TabsList>
            <TabsContent value="columns" className="space-y-4">
              <div className="relative max-w-sm">
                <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
                <Input
                  aria-label="Filter columns"
                  placeholder="Filter by column name or type"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {columns.map((c) => (
                  <ColumnCard key={c.name} col={c} />
                ))}
              </div>
              {columns.length === 0 && <p className="text-sm text-muted-foreground">No columns match “{query}”.</p>}
            </TabsContent>
            <TabsContent value="preview">
              <Card>
                <CardHeader>
                  <CardTitle>Data preview</CardTitle>
                  <CardDescription>The full sheet below the header row, loaded from the server a page at a time.</CardDescription>
                </CardHeader>
                <CardContent>
                  <DataGrid
                    sessionId={session.id}
                    columns={session.column_names}
                    total={session.rows ?? 0}
                    profiles={profile.column_profiles}
                  />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
