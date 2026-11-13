"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { BarChart3, Check, LayoutDashboard, Loader2, Plus, RotateCw, Settings2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";
import {
  analytics,
  type AggRow,
  type Dashboard,
  type DashboardTheme,
  type Field,
  type FieldsResponse,
  type Filter,
  type Query,
  type QueryOutcome,
  type Widget,
} from "@/lib/analytics";
import { CHART_THEMES } from "@/lib/chart-theme";
import { useAnalysisSession } from "@/components/session/session-context";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { TooltipProvider } from "@/components/ui/tooltip";
import { FilterBar } from "./filter-bar";
import { WidgetCard } from "./widget-card";
import { WidgetEditor } from "./widget-editor";

const BATCH = 16;
const newId = () => `w${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
type SaveState = "idle" | "saving" | "saved" | "error";

export function DashboardStudio() {
  const { session } = useAnalysisSession();
  const sid = session.id;
  const [fieldsInfo, setFieldsInfo] = useState<FieldsResponse | null>(null);
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [auto, setAuto] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, QueryOutcome>>({});
  const [loading, setLoading] = useState(false);
  const [customizing, setCustomizing] = useState(false);
  const [editor, setEditor] = useState<{ widget: Widget | null } | null>(null);
  const [confirmRebuild, setConfirmRebuild] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const dirty = useRef(false);

  const fields: Field[] = useMemo(() => fieldsInfo?.fields ?? [], [fieldsInfo]);

  const buildAutomatic = useCallback(async (): Promise<Dashboard> => {
    const rec = await analytics.recommendations(sid);
    setNotes(rec.notes);
    return { theme: "executive", filters: [], widgets: [...rec.kpis, ...rec.charts] };
  }, [sid]);

  // Load fields and the saved dashboard; build the automatic one on the first visit.
  useEffect(() => {
    let stale = false;
    setError(null);
    (async () => {
      try {
        const [f, saved] = await Promise.all([analytics.fields(sid), analytics.dashboard(sid)]);
        if (stale) return;
        setFieldsInfo(f);
        if (saved.saved && saved.dashboard) {
          setDash(saved.dashboard);
        } else {
          const built = await buildAutomatic();
          if (stale) return;
          setAuto(true);
          dirty.current = true;
          setDash(built);
        }
      } catch (e) {
        if (!stale) setError(e instanceof ApiError ? e.message : "The dashboard could not be loaded.");
      }
    })();
    return () => {
      stale = true;
    };
  }, [sid, buildAutomatic]);

  // Every figure comes from the server. Re-run only when queries or filters change, not for layout changes.
  const queryKey = useMemo(() => (dash ? JSON.stringify([dash.widgets.map((w) => [w.id, w.query]), dash.filters]) : ""), [dash]);
  useEffect(() => {
    if (!queryKey) return;
    const [widgets, filters] = JSON.parse(queryKey) as [[string, Query][], Filter[]];
    let stale = false;
    setLoading(true);
    (async () => {
      const next: Record<string, QueryOutcome> = {};
      try {
        for (let i = 0; i < widgets.length; i += BATCH) {
          const chunk = widgets.slice(i, i + BATCH);
          const res = await analytics.run(sid, chunk.map(([, q]) => q), filters);
          chunk.forEach(([id], j) => (next[id] = res.results[j]));
        }
      } catch (e) {
        const message = e instanceof ApiError ? e.message : "The figures could not be calculated.";
        widgets.forEach(([id]) => (next[id] ??= { ok: false, error: { code: "ERROR", message } }));
      }
      if (!stale) {
        setOutcomes(next);
        setLoading(false);
      }
    })();
    return () => {
      stale = true;
    };
  }, [queryKey, sid]);

  // Auto-save shortly after any change.
  useEffect(() => {
    if (!dash || !dirty.current) return;
    setSaveState("saving");
    const t = setTimeout(() => {
      dirty.current = false;
      analytics
        .saveDashboard(sid, dash)
        .then(() => setSaveState("saved"))
        .catch(() => {
          dirty.current = true;
          setSaveState("error");
        });
    }, 600);
    return () => clearTimeout(t);
  }, [dash, sid]);

  // Leaving the page inside the auto-save delay must not lose the last change.
  const latest = useRef<Dashboard | null>(null);
  latest.current = dash;
  useEffect(() => {
    const flush = () => {
      if (!dirty.current || !latest.current) return;
      dirty.current = false;
      void fetch(`/api/sessions/${sid}/dashboard`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(latest.current),
        keepalive: true,
        credentials: "same-origin",
      });
    };
    window.addEventListener("pagehide", flush);
    return () => {
      window.removeEventListener("pagehide", flush);
      flush(); // also when navigating to another screen inside the app
    };
  }, [sid]);

  const update = (fn: (d: Dashboard) => Dashboard) => {
    dirty.current = true;
    setDash((d) => (d ? fn(d) : d));
  };

  const drill = (column: string, row: AggRow) => {
    const filter: Filter = row.missing ? { op: "in", column, values: [], include_missing: true } : { op: "in", column, values: [row.label] };
    update((d) => ({ ...d, filters: [...d.filters.filter((f) => !(f.column === column && f.op === "in")), filter] }));
    toast.success(`Dashboard filtered to ${column} = ${row.missing ? "(missing)" : row.label}. Remove the filter chip to undo.`);
  };

  const rebuild = async () => {
    setConfirmRebuild(false);
    try {
      const built = await buildAutomatic();
      setAuto(true);
      update((d) => ({ ...built, theme: d.theme }));
      toast.success("Dashboard rebuilt from your column types.");
    } catch {
      toast.error("The automatic dashboard could not be built.");
    }
  };

  if (error)
    return (
      <Alert variant="destructive">
        <AlertTitle>Dashboard unavailable</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  if (!dash || !fieldsInfo)
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" role="status" aria-label="Loading dashboard">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28 rounded-2xl" />
        ))}
        <Skeleton className="h-72 rounded-2xl sm:col-span-2 xl:col-span-4" />
      </div>
    );

  const theme = CHART_THEMES[dash.theme];
  const firstOk = Object.values(outcomes).find((o) => o.ok);
  const rowsKept = firstOk?.ok ? firstOk.result.meta.rows_after_filters : null;

  return (
    <TooltipProvider>
      <div className="space-y-4" data-testid="dashboard-studio">
        <div className="flex flex-wrap items-center gap-2 rounded-2xl border bg-card p-3">
          <label className="flex items-center gap-2 text-sm font-medium">
            <span className="sr-only sm:not-sr-only">Theme</span>
            <NativeSelect
              aria-label="Dashboard theme"
              className="w-52"
              value={dash.theme}
              onChange={(e) => update((d) => ({ ...d, theme: e.target.value as DashboardTheme }))}
            >
              {Object.values(CHART_THEMES).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </NativeSelect>
          </label>
          <span className="ml-auto inline-flex items-center gap-1.5 text-xs text-muted-foreground" role="status" data-testid="save-state">
            {saveState === "saving" && (
              <>
                <Loader2 className="size-3.5 animate-spin" aria-hidden /> Saving…
              </>
            )}
            {saveState === "saved" && (
              <>
                <Check className="size-3.5 text-success" aria-hidden /> Saved
              </>
            )}
            {saveState === "error" && <span className="text-destructive-text">Not saved. Changes will be retried.</span>}
          </span>
          <Button variant={customizing ? "default" : "outline"} size="sm" aria-pressed={customizing} onClick={() => setCustomizing((v) => !v)}>
            <Settings2 aria-hidden />
            {customizing ? "Done" : "Customize"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setConfirmRebuild(true)}>
            <RotateCw aria-hidden />
            Rebuild automatically
          </Button>
          <Button size="sm" onClick={() => setEditor({ widget: null })} disabled={dash.widgets.length >= 24}>
            <Plus aria-hidden />
            Add widget
          </Button>
        </div>

        {auto && (
          <Alert data-testid="auto-note">
            <Sparkles aria-hidden />
            <AlertTitle>Built automatically from your column types</AlertTitle>
            <AlertDescription>
              <p>
                Each widget was chosen by a fixed rule, shown under its <span className="font-medium">i</span> icon. Column names are not used to guess
                what the data means. Every figure is calculated from all {fieldsInfo.rows.toLocaleString("en-US")} rows of your current data.
              </p>
              {notes.length > 0 && (
                <ul className="mt-1 list-disc pl-5">
                  {notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              )}
            </AlertDescription>
          </Alert>
        )}

        <FilterBar filters={dash.filters} fields={fields} rowsKept={rowsKept} rowsTotal={fieldsInfo.rows} onChange={(filters) => update((d) => ({ ...d, filters }))} />

        <div className="rounded-3xl border p-3 sm:p-4" style={{ background: theme.canvas, borderColor: theme.cardBorder }} data-testid="dashboard-canvas" data-theme-id={theme.id}>
          {dash.widgets.length === 0 ? (
            <EmptyState
              icon={LayoutDashboard}
              title="This dashboard is empty"
              description="Add a widget, or rebuild the automatic dashboard from your column types."
              action={
                <Button onClick={() => setEditor({ widget: null })}>
                  <Plus aria-hidden />
                  Add widget
                </Button>
              }
            />
          ) : (
            <div className="grid grid-cols-12 gap-3 sm:gap-4">
              {dash.widgets.map((w, i) => (
                <WidgetCard
                  key={w.id}
                  widget={w}
                  outcome={outcomes[w.id]}
                  loading={loading}
                  theme={theme}
                  customizing={customizing}
                  isFirst={i === 0}
                  isLast={i === dash.widgets.length - 1}
                  onEdit={() => setEditor({ widget: w })}
                  onRemove={() => update((d) => ({ ...d, widgets: d.widgets.filter((x) => x.id !== w.id) }))}
                  onMove={(delta) =>
                    update((d) => {
                      const widgets = [...d.widgets];
                      const j = i + delta;
                      if (j < 0 || j >= widgets.length) return d;
                      [widgets[i], widgets[j]] = [widgets[j], widgets[i]];
                      return { ...d, widgets };
                    })
                  }
                  onDrill={drill}
                />
              ))}
            </div>
          )}
        </div>

        <p className="flex flex-wrap items-center gap-x-1 text-xs text-muted-foreground">
          <BarChart3 className="size-3.5" aria-hidden />
          Figures reflect your current data (version {fieldsInfo.version}). Fix data problems in the{" "}
          <Link href={`/s/${sid}/clean`} className="text-link underline underline-offset-2">
            Cleaning Studio
          </Link>{" "}
          and the dashboard updates.
        </p>

        <WidgetEditor
          open={editor !== null}
          widget={editor?.widget ?? null}
          fields={fields}
          sessionId={sid}
          filters={dash.filters}
          theme={theme}
          onClose={() => setEditor(null)}
          onSave={(w) => {
            update((d) =>
              w.id
                ? { ...d, widgets: d.widgets.map((x) => (x.id === w.id ? ({ ...w, id: x.id } as Widget) : x)) }
                : { ...d, widgets: [...d.widgets, { ...w, id: newId() } as Widget] },
            );
            setEditor(null);
          }}
        />

        <AlertDialog open={confirmRebuild} onOpenChange={setConfirmRebuild}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Rebuild the dashboard automatically?</AlertDialogTitle>
              <AlertDialogDescription>
                This replaces all {dash.widgets.length} widgets and removes the filters. Your data and cleaning steps are not affected.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep my dashboard</AlertDialogCancel>
              <AlertDialogAction onClick={rebuild}>Rebuild</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </TooltipProvider>
  );
}
