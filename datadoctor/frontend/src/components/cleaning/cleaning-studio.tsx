"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  ArrowLeftRight, CalendarCheck, CaseSensitive, Check, Columns3, Copy, Eraser, Eye, FileWarning, Hash, History, Loader2,
  RotateCcw, Rows3, ScanSearch, Space, SquareDashed, Tags, Trash2, Undo2, Wand2,
} from "lucide-react";
import { toast } from "sonner";
import {
  api, ApiError, type ColumnProfile, type OperationSpec, type OpPreview, type Profile, type Timeline,
} from "@/lib/api";
import { formatInteger } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useAnalysisSession } from "@/components/session/session-context";
import { DataGrid } from "@/components/health/data-grid";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CompareView } from "./compare-view";
import { Field, type Values } from "./fields";
import { HistoryTimeline } from "./history-timeline";
import { PreviewPanel } from "./preview-panel";

const ICONS: Record<string, typeof Wand2> = {
  remove_exact_duplicates: Copy, key_duplicates: ScanSearch, remove_empty_rows: Rows3, trim_whitespace: Eraser,
  normalize_spaces: Space, standardize_case: CaseSensitive, normalize_categories: Tags, convert_numeric: Hash,
  normalize_dates: CalendarCheck, identify_invalid_dates: FileWarning, detect_missing: SquareDashed,
  handle_missing: SquareDashed, rename_columns: Columns3, reorder_columns: Columns3, remove_columns: Trash2,
  flag_outliers: ScanSearch, flag_types: ScanSearch,
};

function defaults(spec: OperationSpec): Values {
  const v: Values = {};
  for (const f of spec.fields) {
    if (f.default !== undefined) v[f.name] = f.default;
    else if (f.kind === "columns" || f.kind === "tokens") v[f.name] = [];
  }
  return v;
}

/** Parameters to send: drop empty optional values and fields hidden by show_if. */
function payload(spec: OperationSpec, values: Values): Values {
  const out: Values = {};
  for (const f of spec.fields) {
    if (f.show_if && !Object.entries(f.show_if).every(([k, v]) => values[k] === v)) continue;
    const v = values[f.name];
    if (v === undefined || v === null || v === "") continue;
    out[f.name] = v;
  }
  return out;
}

export function CleaningStudio() {
  const { session, setSession } = useAnalysisSession();
  const params = useSearchParams();
  const [specs, setSpecs] = useState<OperationSpec[] | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [historyBusy, setHistoryBusy] = useState<"undo" | "reset" | null>(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [values, setValues] = useState<Values>({});
  const [preview, setPreview] = useState<OpPreview | null>(null);
  const [busy, setBusy] = useState<"preview" | "apply" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [formKey, setFormKey] = useState(0);

  useEffect(() => {
    api.operations().then(setSpecs).catch(() => setError("Could not load the cleaning tools."));
  }, []);
  const loadSide = useCallback(() => {
    api.profile(session.id).then(setProfile).catch(() => setProfile(null));
    api.timeline(session.id).then(setTimeline).catch(() => setTimeline(null));
  }, [session.id]);
  useEffect(loadSide, [loadSide, session.version]);

  const spec = specs?.find((s) => s.id === selected) ?? null;
  const profiles = useMemo(
    () => new Map<string, ColumnProfile>((profile?.column_profiles ?? []).map((p) => [p.name, p])),
    [profile],
  );

  const choose = useCallback(
    (id: string, preset: Values = {}) => {
      const s = specs?.find((x) => x.id === id);
      if (!s) return;
      setSelected(id);
      setValues({ ...defaults(s), ...preset });
      setPreview(null);
      setError(null);
      setFormKey((k) => k + 1);
    },
    [specs],
  );

  // Deep link from the Data Health Center: ?op=trim_whitespace&column=City
  useEffect(() => {
    const op = params.get("op");
    if (!specs || !op) return;
    const column = params.get("column");
    const s = specs.find((x) => x.id === op);
    const preset: Values = {};
    if (s && column) {
      if (s.fields.some((f) => f.name === "column")) preset.column = column;
      else if (s.fields.some((f) => f.name === "columns")) preset.columns = [column];
    }
    choose(op, preset);
  }, [specs, params, choose]);

  const setValue = (name: string, value: unknown) => {
    setValues((v) => ({ ...v, [name]: value }));
    setPreview(null);
  };

  async function runPreview() {
    if (!spec) return;
    setBusy("preview");
    setError(null);
    try {
      setPreview(await api.previewOp(session.id, spec.id, payload(spec, values)));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Preview failed.");
    } finally {
      setBusy(null);
    }
  }

  async function apply(confirm: boolean) {
    if (!spec || !preview) return;
    setBusy("apply");
    setError(null);
    try {
      const res = await api.applyOp(session.id, spec.id, payload(spec, values), confirm);
      setSession(res.session);
      toast.success(`${spec.title}: ${res.result.summary}`);
      setPreview(null);
      setValues(defaults(spec));
      setFormKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The change could not be applied.");
    } finally {
      setBusy(null);
      setConfirmOpen(false);
    }
  }

  const groups = useMemo(() => {
    const g = new Map<string, OperationSpec[]>();
    specs?.forEach((s) => g.set(s.group, [...(g.get(s.group) ?? []), s]));
    return [...g.entries()];
  }, [specs]);
  const active = (timeline?.operations ?? []).filter((h) => h.status === "active");
  const last = active[active.length - 1];

  async function undo() {
    setHistoryBusy("undo");
    try {
      const res = await api.undo(session.id);
      setSession(res.session);
      toast.success(`Undid “${last?.title ?? "last change"}”`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not undo.");
    } finally {
      setHistoryBusy(null);
    }
  }

  async function reset() {
    setHistoryBusy("reset");
    try {
      const res = await api.reset(session.id);
      setSession(res.session);
      toast.success(`Reset to the original data (${res.undone.length} change${res.undone.length === 1 ? "" : "s"} undone)`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not reset.");
    } finally {
      setHistoryBusy(null);
      setResetOpen(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-xl border bg-card px-4 py-3 sm:flex-row sm:items-center" data-testid="history-bar">
        <p className="text-sm">
          {active.length === 0 ? (
            <span className="text-muted-foreground">No changes applied: you are looking at the original data.</span>
          ) : (
            <>
              <span className="font-medium">{active.length} change{active.length === 1 ? "" : "s"} applied.</span>{" "}
              <span className="text-muted-foreground">Last: {last?.title}</span>
            </>
          )}
        </p>
        <div className="flex flex-wrap gap-2 sm:ml-auto">
          <Button variant="outline" size="sm" disabled={!active.length || historyBusy !== null || busy !== null} onClick={undo}>
            {historyBusy === "undo" ? <Loader2 className="animate-spin" /> : <Undo2 />} Undo last change
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!active.length || historyBusy !== null || busy !== null}
            onClick={() => setResetOpen(true)}
          >
            {historyBusy === "reset" ? <Loader2 className="animate-spin" /> : <RotateCcw />} Reset to original
          </Button>
        </div>
      </div>

      <AlertDialog open={resetOpen} onOpenChange={setResetOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset to the original data?</AlertDialogTitle>
            <AlertDialogDescription>
              All {active.length} applied change{active.length === 1 ? "" : "s"} will be undone and the working copy will match your
              uploaded file again. The steps stay in the history for your audit trail.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction destructive onClick={reset}>
              Reset everything
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <div className="grid items-start gap-6 lg:grid-cols-[17rem_minmax(0,1fr)]">
        {/* Tool palette */}
        <Card className="gap-2 py-4">
          <CardHeader className="px-4">
            <CardTitle className="text-sm">Cleaning tools</CardTitle>
          </CardHeader>
          <CardContent className="px-2">
            <div className="px-2 lg:hidden">
              <NativeSelect aria-label="Choose a cleaning tool" value={selected ?? ""} onChange={(e) => choose(e.target.value)}>
                <option value="" disabled>
                  Choose a cleaning tool…
                </option>
                {groups.map(([group, items]) => (
                  <optgroup key={group} label={group}>
                    {items.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.title}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </NativeSelect>
            </div>
            <nav aria-label="Cleaning tools" className="hidden space-y-3 lg:block">
              {!specs && <Skeleton className="h-96" />}
              {groups.map(([group, items]) => (
                <div key={group}>
                  <p className="px-2 pb-1 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">{group}</p>
                  <ul>
                    {items.map((s) => {
                      const Icon = ICONS[s.id] ?? Wand2;
                      return (
                        <li key={s.id}>
                          <button
                            type="button"
                            onClick={() => choose(s.id)}
                            aria-current={selected === s.id ? "true" : undefined}
                            className={cn(
                              "flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
                              selected === s.id && "bg-accent font-medium text-accent-foreground",
                            )}
                          >
                            <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                            {s.title}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </nav>
          </CardContent>
        </Card>

        {/* Operation form + preview */}
        <Card className="min-w-0">
          {!spec ? (
            <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
              <Wand2 className="size-10 text-primary" aria-hidden />
              <p className="font-semibold">Choose a cleaning tool</p>
              <p className="max-w-md text-sm text-muted-foreground">
                Every change is previewed on your full data before it is applied. Your original file is never modified.
              </p>
            </CardContent>
          ) : (
            <>
              <CardHeader>
                <CardTitle className="flex flex-wrap items-center gap-2">
                  {spec.title}
                  {spec.always_destructive && <Badge variant="warning">Removes data</Badge>}
                </CardTitle>
                <CardDescription>{spec.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <form
                  key={formKey}
                  className="grid gap-4 md:max-w-xl"
                  onSubmit={(e) => {
                    e.preventDefault();
                    runPreview();
                  }}
                  aria-label={`${spec.title} settings`}
                >
                  {spec.fields.map((f) => (
                    <Field
                      key={f.name}
                      field={f}
                      values={values}
                      setValue={setValue}
                      columns={session.column_names}
                      profiles={profiles}
                      sessionId={session.id}
                    />
                  ))}
                  {spec.fields.length === 0 && <p className="text-sm text-muted-foreground">No settings needed.</p>}
                  <div>
                    <Button type="submit" variant="outline" disabled={busy !== null}>
                      {busy === "preview" ? <Loader2 className="animate-spin" /> : <Eye />} Preview on full data
                    </Button>
                  </div>
                </form>

                {error && (
                  <Alert variant="destructive">
                    <FileWarning aria-hidden />
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                )}

                {preview && (
                  <div className="space-y-4 border-t pt-5">
                    <PreviewPanel preview={preview} />
                    <div className="flex flex-wrap items-center gap-3">
                      <Button
                        disabled={busy !== null || preview.affected_rows === 0}
                        variant={preview.destructive ? "destructive" : "default"}
                        onClick={() => (preview.destructive ? setConfirmOpen(true) : apply(false))}
                      >
                        {busy === "apply" ? <Loader2 className="animate-spin" /> : <Check />} Apply change
                      </Button>
                      {preview.affected_rows === 0 && <span className="text-sm text-muted-foreground">Nothing to change.</span>}
                    </div>
                  </div>
                )}
              </CardContent>
            </>
          )}
        </Card>
      </div>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Apply “{spec?.title}”?</AlertDialogTitle>
            <AlertDialogDescription>
              {preview?.removed_rows
                ? `${formatInteger(preview.removed_rows)} row(s) will be removed from the working copy.`
                : preview?.removed_columns.length
                  ? `${preview.removed_columns.length} column(s) will be removed from the working copy.`
                  : `${formatInteger(preview?.affected_rows ?? 0)} row(s) will be changed.`}{" "}
              Your original file is kept and you can undo this later.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction destructive onClick={() => apply(true)}>
              Yes, apply
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Tabs defaultValue="current">
        <TabsList>
          <TabsTrigger value="current">
            <Rows3 aria-hidden /> Current data
          </TabsTrigger>
          <TabsTrigger value="original">
            <Eye aria-hidden /> Original
          </TabsTrigger>
          <TabsTrigger value="compare">
            <ArrowLeftRight aria-hidden /> Before / after
          </TabsTrigger>
          <TabsTrigger value="history">
            <History aria-hidden /> History ({timeline?.events.length ?? 0})
          </TabsTrigger>
        </TabsList>
        <TabsContent value="current">
          <DataGrid sessionId={session.id} columns={session.column_names} total={session.rows ?? 0} version={session.version} />
        </TabsContent>
        <TabsContent value="original">
          <OriginalGrid sessionId={session.id} />
        </TabsContent>
        <TabsContent value="compare">
          <CompareView sessionId={session.id} columns={session.column_names} version={session.version} />
        </TabsContent>
        <TabsContent value="history">
          {timeline ? <HistoryTimeline timeline={timeline} /> : <Skeleton className="h-32" />}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function OriginalGrid({ sessionId }: { sessionId: string }) {
  const [meta, setMeta] = useState<{ columns: string[]; total: number } | null>(null);
  useEffect(() => {
    api.rows(sessionId, 0, 1, "original").then((r) => setMeta({ columns: r.columns, total: r.total })).catch(() => setMeta(null));
  }, [sessionId]);
  if (!meta) return <Skeleton className="h-64" />;
  return <DataGrid sessionId={sessionId} columns={meta.columns} total={meta.total} view="original" />;
}
