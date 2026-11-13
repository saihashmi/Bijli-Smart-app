"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Columns3, Copy, FileWarning, Grid3x3, Info, ListChecks, Loader2, RotateCw, Rows3, Ruler, Search, SquareDashed } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, type Profile } from "@/lib/api";
import { formatInteger } from "@/lib/format";
import { useAnalysisSession } from "@/components/session/session-context";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Reveal } from "@/components/ui/reveal";
import { StatTile } from "@/components/ui/stat-tile";
import { ColumnCard } from "./column-card";
import { QualityDistribution, SeverityBreakdown, TypeDistribution } from "./distributions";
import { MissingHeatmap } from "./heatmap";
import { DataGrid } from "./data-grid";
import { IssueList } from "./issue-list";
import { MissingChart } from "./missing-chart";
import { ScoreCard } from "./score-card";

const plural = (n: number, word: string) => `${formatInteger(n)} ${word}${n === 1 ? "" : "s"}`;

export function HealthView() {
  const { session } = useAnalysisSession();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [busyColumn, setBusyColumn] = useState<string | null>(null);

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

  async function setSensitive(column: string, on: boolean) {
    if (!profile) return;
    const current = new Set(profile.sensitive_columns);
    if (on) current.add(column);
    else current.delete(column);
    setBusyColumn(column);
    try {
      await api.setSensitive(session.id, [...current]);
      setProfile(await api.profile(session.id));
      toast.success(on ? `“${column}” marked as sensitive` : `“${column}” is no longer marked sensitive`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not update the column.");
    } finally {
      setBusyColumn(null);
    }
  }

  // Tiles derived from the issue list (cells/rows counted by the server).
  const sumIssues = (codes: string[]) =>
    (profile?.issues ?? []).filter((i) => codes.includes(i.code)).reduce((a, i) => a + i.affected_rows, 0);
  const invalid = sumIssues(["Q09", "Q12"]);
  const inconsistent = sumIssues(["Q05", "Q06", "Q07", "Q08", "Q10"]);

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
            <Loader2 className="size-4 animate-spin" aria-hidden /> Checking {formatInteger(session.rows ?? 0)} rows ×{" "}
            {formatInteger(session.columns ?? 0)} columns…
          </p>
          <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
            <Skeleton className="h-96 rounded-xl" />
            <div className="grid grid-cols-2 gap-3">
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-24 rounded-xl" />
              ))}
            </div>
          </div>
        </div>
      )}

      {profile && (
        <>
          <div className="grid items-stretch gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
            <Reveal>
              <ScoreCard health={profile.health} />
            </Reveal>
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-3 xl:grid-cols-3" data-testid="health-kpis">
                <StatTile icon={Rows3} label="Rows" value={formatInteger(profile.rows)} sub={plural(profile.columns, "column")} />
                <StatTile icon={Columns3} label="Columns" value={formatInteger(profile.columns)} sub={profile.empty_columns ? `${plural(profile.empty_columns, "empty column")}` : "None empty"} />
                <StatTile
                  icon={SquareDashed}
                  label="Missing values"
                  tone={profile.missing_pct > 20 ? "bad" : profile.missing_pct >= 5 ? "warn" : "good"}
                  value={`${profile.missing_pct}%`}
                  sub={`${formatInteger(profile.missing_cells)} of ${formatInteger(profile.total_cells)} cells`}
                />
                <StatTile
                  icon={Copy}
                  label="Exact duplicate rows"
                  tone={profile.duplicate_rows ? "warn" : "good"}
                  value={formatInteger(profile.duplicate_rows)}
                  sub={profile.empty_rows ? `${plural(profile.empty_rows, "completely empty row")}` : "No empty rows"}
                />
                <StatTile
                  icon={FileWarning}
                  label="Invalid values"
                  tone={invalid ? "warn" : "good"}
                  value={formatInteger(invalid)}
                  sub="Impossible dates and values of the wrong type"
                />
                <StatTile
                  icon={Ruler}
                  label="Inconsistent formats"
                  tone={inconsistent ? "warn" : "good"}
                  value={formatInteger(inconsistent)}
                  sub="Spacing, spelling variants, text numbers, mixed date formats"
                />
              </div>
              <div className="grid gap-6 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Issues by severity</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <SeverityBreakdown counts={profile.issue_counts} />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Columns</CardTitle>
                    <CardDescription>By detected data type and by quality (values present × matching the column type).</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <TypeDistribution columns={profile.column_profiles} />
                    <QualityDistribution columns={profile.column_profiles} />
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Missing-value map</CardTitle>
                <CardDescription>Where in the sheet values are missing. Hover a block for its rows.</CardDescription>
              </CardHeader>
              <CardContent>
                {profile.missing_map ? (
                  <MissingHeatmap map={profile.missing_map} totalRows={profile.rows} />
                ) : (
                  <p className="text-sm text-muted-foreground">Not available for this dataset.</p>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Missing values by column</CardTitle>
              </CardHeader>
              <CardContent>
                <MissingChart columns={profile.column_profiles} />
              </CardContent>
            </Card>
          </div>

          <Tabs defaultValue="issues">
            <TabsList>
              <TabsTrigger value="issues">
                <ListChecks aria-hidden /> Issues ({profile.issues.length})
              </TabsTrigger>
              <TabsTrigger value="columns">
                <Grid3x3 aria-hidden /> Column profiles
              </TabsTrigger>
              <TabsTrigger value="preview">
                <Rows3 aria-hidden /> Data preview
              </TabsTrigger>
            </TabsList>
            <TabsContent value="issues">
              <IssueList
                sessionId={session.id}
                issues={profile.issues}
                busyColumn={busyColumn}
                onMarkSensitive={(c) => setSensitive(c, true)}
              />
            </TabsContent>
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
                  <ColumnCard
                    key={c.name}
                    col={c}
                    sensitive={profile.sensitive_columns.includes(c.name)}
                    busy={busyColumn === c.name}
                    onToggleSensitive={() => setSensitive(c.name, !profile.sensitive_columns.includes(c.name))}
                  />
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
                    version={session.version}
                    profiles={profile.column_profiles}
                    showFlags
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
