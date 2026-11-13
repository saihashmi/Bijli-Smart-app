"use client";

import { useEffect, useId, useMemo, useState } from "react";
import {
  AGG_LABEL,
  analytics,
  CHART_LABEL,
  type Agg,
  type ChartType,
  type Field,
  type Filter,
  type Grain,
  type Query,
  type QueryOutcome,
  type Widget,
  type WidgetWidth,
} from "@/lib/analytics";
import type { ChartTheme } from "@/lib/chart-theme";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { ChartBody, emptyReason } from "./charts";

const CHARTS: ChartType[] = ["kpi", "bar", "line", "area", "pie", "donut", "histogram", "scatter", "table"];
const GRAINS: Grain[] = ["day", "week", "month", "quarter", "year"];
const ROWS = "__rows__";
const NONE = "__none__";

/** Everything the form edits, flattened. Converted to a validated Query by `toQuery`. */
type Draft = {
  title: string;
  titleEdited: boolean;
  chart: ChartType;
  width: WidgetWidth;
  measureColumn: string; // ROWS = count rows
  agg: Agg;
  dimension: string; // NONE
  grain: Grain;
  series: string; // NONE
  sortBy: "value" | "label";
  sortDir: "asc" | "desc";
  limit: string;
  column: string;
  bins: string;
  x: string;
  y: string;
  columns: string[];
};

function fromWidget(w: Widget | null, fields: Field[]): Draft {
  const numeric = fields.filter((f) => f.kind === "number");
  const d: Draft = {
    title: w?.title ?? "",
    titleEdited: Boolean(w),
    chart: w?.chart ?? "bar",
    width: w?.width ?? 6,
    measureColumn: ROWS,
    agg: "count",
    dimension: fields.find((f) => f.can_group)?.name ?? NONE,
    grain: "month",
    series: NONE,
    sortBy: "value",
    sortDir: "desc",
    limit: "10",
    column: numeric[0]?.name ?? "",
    bins: "20",
    x: numeric[0]?.name ?? "",
    y: numeric[1]?.name ?? "",
    columns: fields.slice(0, 6).map((f) => f.name),
  };
  const q = w?.query;
  if (!q) return d;
  if (q.kind === "aggregate") {
    d.measureColumn = q.measure.column ?? ROWS;
    d.agg = q.measure.agg;
    d.dimension = q.dimension?.column ?? NONE;
    d.grain = q.dimension?.grain ?? "month";
    d.series = q.series ?? NONE;
    d.sortBy = q.sort?.by ?? (q.dimension?.grain ? "label" : "value");
    d.sortDir = q.sort?.dir ?? (q.dimension?.grain ? "asc" : "desc");
    d.limit = q.limit ? String(q.limit) : "";
  } else if (q.kind === "histogram") {
    d.column = q.column;
    d.bins = String(q.bins ?? 20);
  } else if (q.kind === "scatter") {
    d.x = q.x;
    d.y = q.y;
  } else if (q.columns?.length) d.columns = q.columns;
  return d;
}

function toQuery(d: Draft, fields: Field[]): { query: Query | null; problem: string | null } {
  const kind = (name: string) => fields.find((f) => f.name === name)?.kind;
  if (d.chart === "histogram") {
    if (!d.column) return { query: null, problem: "A histogram needs a numeric column, and this data has none." };
    return { query: { kind: "histogram", column: d.column, bins: Math.min(60, Math.max(2, Number(d.bins) || 20)) }, problem: null };
  }
  if (d.chart === "scatter") {
    if (!d.x || !d.y) return { query: null, problem: "A scatter plot needs two numeric columns." };
    if (d.x === d.y) return { query: null, problem: "Choose two different columns." };
    return { query: { kind: "scatter", x: d.x, y: d.y }, problem: null };
  }
  if (d.chart === "table") {
    if (!d.columns.length) return { query: null, problem: "Choose at least one column." };
    return { query: { kind: "table", columns: d.columns, limit: 25 }, problem: null };
  }
  const measure = d.measureColumn === ROWS ? { agg: "count" as Agg } : { agg: d.agg, column: d.measureColumn };
  if (d.chart === "kpi") return { query: { kind: "aggregate", measure }, problem: null };
  if (d.dimension === NONE) return { query: null, problem: "Choose a column to group by." };
  const isDate = kind(d.dimension) === "date";
  const limit = Number(d.limit);
  return {
    query: {
      kind: "aggregate",
      measure,
      dimension: { column: d.dimension, ...(isDate ? { grain: d.grain } : {}) },
      ...(d.series !== NONE && ["bar", "line", "area"].includes(d.chart) ? { series: d.series } : {}),
      sort: { by: d.sortBy, dir: d.sortDir },
      ...(Number.isInteger(limit) && limit >= 1 ? { limit: Math.min(limit, 500) } : {}),
    },
    problem: null,
  };
}

function autoTitle(d: Draft): string {
  const measure = d.measureColumn === ROWS ? "Rows" : `${AGG_LABEL[d.agg]} of ${d.measureColumn}`;
  if (d.chart === "kpi") return measure;
  if (d.chart === "histogram") return d.column ? `Distribution of ${d.column}` : "Histogram";
  if (d.chart === "scatter") return d.x && d.y ? `${d.y} against ${d.x}` : "Scatter";
  if (d.chart === "table") return "Rows";
  return d.dimension === NONE ? measure : `${measure} by ${d.dimension}${d.series !== NONE ? ` and ${d.series}` : ""}`;
}

function Row({ label, htmlFor, children, hint }: { label: string; htmlFor?: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function WidgetEditor({
  open,
  widget,
  fields,
  sessionId,
  filters,
  theme,
  onClose,
  onSave,
}: {
  open: boolean;
  widget: Widget | null;
  fields: Field[];
  sessionId: string;
  filters: Filter[];
  theme: ChartTheme;
  onClose: () => void;
  onSave: (w: Omit<Widget, "id"> & { id?: string }) => void;
}) {
  const uid = useId();
  const [d, setD] = useState<Draft>(() => fromWidget(widget, fields));
  const [preview, setPreview] = useState<QueryOutcome | null>(null);
  const set = (patch: Partial<Draft>) => setD((prev) => ({ ...prev, ...patch }));

  useEffect(() => {
    if (open) {
      setD(fromWidget(widget, fields));
      setPreview(null);
    }
  }, [open, widget, fields]);

  const numeric = useMemo(() => fields.filter((f) => f.kind === "number"), [fields]);
  const groupable = useMemo(() => fields.filter((f) => f.can_group), [fields]);
  const measurable = useMemo(() => fields.filter((f) => f.aggregations.length > 0), [fields]);
  const measureField = fields.find((f) => f.name === d.measureColumn);
  const aggs: Agg[] = measureField?.aggregations ?? ["count"];
  const dimKind = fields.find((f) => f.name === d.dimension)?.kind;
  const grouped = ["bar", "line", "area", "pie", "donut"].includes(d.chart);

  const { query, problem } = useMemo(() => toQuery(d, fields), [d, fields]);
  const queryKey = query ? JSON.stringify(query) : "";
  const filterKey = JSON.stringify(filters);

  // Live preview, calculated by the server from the full data (never estimated in the browser).
  useEffect(() => {
    if (!open || !queryKey) return;
    let stale = false;
    const t = setTimeout(() => {
      analytics
        .run(sessionId, [JSON.parse(queryKey) as Query], JSON.parse(filterKey) as Filter[])
        .then((r) => !stale && setPreview(r.results[0]))
        .catch(() => !stale && setPreview({ ok: false, error: { code: "ERROR", message: "The preview could not be calculated." } }));
    }, 250);
    return () => {
      stale = true;
      clearTimeout(t);
    };
  }, [open, queryKey, filterKey, sessionId]);

  const title = d.titleEdited ? d.title : autoTitle(d);
  const result = query && preview?.ok ? preview.result : null;
  const reason = result ? emptyReason(d.chart, result) : null;
  const previewError = problem ?? (preview && !preview.ok ? preview.error.message : null);

  const pickMeasure = (name: string) => {
    const f = fields.find((x) => x.name === name);
    set({ measureColumn: name, agg: f ? (f.aggregations.includes(d.agg) ? d.agg : f.aggregations[0]) : "count" });
  };

  const save = () => {
    if (!query || !title.trim()) return;
    onSave({ id: widget?.id, title: title.trim().slice(0, 120), chart: d.chart, query, width: d.chart === "kpi" && !widget ? 3 : d.width, reason: null });
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-4xl" data-testid="widget-editor">
        <DialogHeader>
          <DialogTitle>{widget ? "Edit widget" : "Add a widget"}</DialogTitle>
          <DialogDescription>Only combinations that make sense for your columns are offered. The preview is calculated from your full data.</DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="space-y-4">
            <Row label="Chart type" htmlFor={`${uid}-chart`}>
              <NativeSelect id={`${uid}-chart`} value={d.chart} onChange={(e) => set({ chart: e.target.value as ChartType })}>
                {CHARTS.map((c) => (
                  <option key={c} value={c} disabled={(c === "histogram" && !numeric.length) || (c === "scatter" && numeric.length < 2)}>
                    {CHART_LABEL[c]}
                    {c === "histogram" && !numeric.length ? " (needs a numeric column)" : ""}
                    {c === "scatter" && numeric.length < 2 ? " (needs two numeric columns)" : ""}
                  </option>
                ))}
              </NativeSelect>
            </Row>

            {(d.chart === "kpi" || grouped) && (
              <div className="grid gap-3 sm:grid-cols-2">
                <Row label="Value" htmlFor={`${uid}-measure`}>
                  <NativeSelect id={`${uid}-measure`} value={d.measureColumn} onChange={(e) => pickMeasure(e.target.value)}>
                    <option value={ROWS}>Number of rows</option>
                    {measurable.map((f) => (
                      <option key={f.name} value={f.name}>
                        {f.name} ({f.kind})
                      </option>
                    ))}
                  </NativeSelect>
                </Row>
                <Row label="Calculation" htmlFor={`${uid}-agg`}>
                  <NativeSelect id={`${uid}-agg`} value={d.measureColumn === ROWS ? "count" : d.agg} disabled={d.measureColumn === ROWS} onChange={(e) => set({ agg: e.target.value as Agg })}>
                    {aggs.map((a) => (
                      <option key={a} value={a}>
                        {AGG_LABEL[a]}
                      </option>
                    ))}
                  </NativeSelect>
                </Row>
              </div>
            )}
            {(d.chart === "kpi" || grouped) && measureField && measureField.kind !== "number" && (
              <p className="-mt-2 text-xs text-muted-foreground">
                “{measureField.name}” is {measureField.kind}, so it can be counted but not summed or averaged.
              </p>
            )}

            {grouped && (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Row label="Group by" htmlFor={`${uid}-dim`}>
                    <NativeSelect id={`${uid}-dim`} value={d.dimension} onChange={(e) => set({ dimension: e.target.value })}>
                      {!groupable.length && <option value={NONE}>No column can be grouped</option>}
                      {groupable.map((f) => (
                        <option key={f.name} value={f.name}>
                          {f.name} ({f.kind}, {f.kind === "date" ? "dates" : `${f.unique} values`})
                        </option>
                      ))}
                    </NativeSelect>
                  </Row>
                  {dimKind === "date" ? (
                    <Row label="Period" htmlFor={`${uid}-grain`}>
                      <NativeSelect id={`${uid}-grain`} value={d.grain} onChange={(e) => set({ grain: e.target.value as Grain, sortBy: "label", sortDir: "asc" })}>
                        {GRAINS.map((g) => (
                          <option key={g} value={g}>
                            {g[0].toUpperCase() + g.slice(1)}
                          </option>
                        ))}
                      </NativeSelect>
                    </Row>
                  ) : (
                    <Row label="Show top" htmlFor={`${uid}-limit`} hint="The rest is combined as “Other”.">
                      <Input id={`${uid}-limit`} type="number" min={1} max={500} value={d.limit} onChange={(e) => set({ limit: e.target.value })} />
                    </Row>
                  )}
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Row label="Sort" htmlFor={`${uid}-sort`}>
                    <NativeSelect
                      id={`${uid}-sort`}
                      value={`${d.sortBy}:${d.sortDir}`}
                      onChange={(e) => {
                        const [by, dir] = e.target.value.split(":") as [Draft["sortBy"], Draft["sortDir"]];
                        set({ sortBy: by, sortDir: dir });
                      }}
                    >
                      <option value="value:desc">Largest value first</option>
                      <option value="value:asc">Smallest value first</option>
                      <option value="label:asc">{dimKind === "date" ? "Oldest first" : "Label A to Z"}</option>
                      <option value="label:desc">{dimKind === "date" ? "Newest first" : "Label Z to A"}</option>
                    </NativeSelect>
                  </Row>
                  {["bar", "line", "area"].includes(d.chart) && (
                    <Row label="Split into series (optional)" htmlFor={`${uid}-series`}>
                      <NativeSelect id={`${uid}-series`} value={d.series} onChange={(e) => set({ series: e.target.value })}>
                        <option value={NONE}>No split</option>
                        {groupable
                          .filter((f) => f.kind !== "date" && f.name !== d.dimension)
                          .map((f) => (
                            <option key={f.name} value={f.name}>
                              {f.name} ({f.unique} values)
                            </option>
                          ))}
                      </NativeSelect>
                    </Row>
                  )}
                </div>
              </>
            )}

            {d.chart === "histogram" && (
              <div className="grid gap-3 sm:grid-cols-2">
                <Row label="Numeric column" htmlFor={`${uid}-hcol`}>
                  <NativeSelect id={`${uid}-hcol`} value={d.column} onChange={(e) => set({ column: e.target.value })}>
                    {numeric.map((f) => (
                      <option key={f.name}>{f.name}</option>
                    ))}
                  </NativeSelect>
                </Row>
                <Row label="Number of bars" htmlFor={`${uid}-bins`}>
                  <Input id={`${uid}-bins`} type="number" min={2} max={60} value={d.bins} onChange={(e) => set({ bins: e.target.value })} />
                </Row>
              </div>
            )}

            {d.chart === "scatter" && (
              <div className="grid gap-3 sm:grid-cols-2">
                <Row label="Horizontal (X)" htmlFor={`${uid}-x`}>
                  <NativeSelect id={`${uid}-x`} value={d.x} onChange={(e) => set({ x: e.target.value })}>
                    {numeric.map((f) => (
                      <option key={f.name}>{f.name}</option>
                    ))}
                  </NativeSelect>
                </Row>
                <Row label="Vertical (Y)" htmlFor={`${uid}-y`}>
                  <NativeSelect id={`${uid}-y`} value={d.y} onChange={(e) => set({ y: e.target.value })}>
                    {numeric.map((f) => (
                      <option key={f.name}>{f.name}</option>
                    ))}
                  </NativeSelect>
                </Row>
              </div>
            )}

            {d.chart === "table" && (
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium">Columns</legend>
                <div className="grid max-h-40 gap-1.5 overflow-y-auto rounded-md border p-2 sm:grid-cols-2">
                  {fields.map((f) => (
                    <label key={f.name} className="flex cursor-pointer items-center gap-2 text-sm">
                      <Checkbox
                        checked={d.columns.includes(f.name)}
                        onCheckedChange={(on) => set({ columns: on ? [...d.columns, f.name].slice(0, 30) : d.columns.filter((c) => c !== f.name) })}
                      />
                      <span className="truncate">{f.name}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            )}

            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_9rem]">
              <Row label="Title" htmlFor={`${uid}-title`}>
                <Input id={`${uid}-title`} value={title} maxLength={120} onChange={(e) => set({ title: e.target.value, titleEdited: true })} />
              </Row>
              <Row label="Width" htmlFor={`${uid}-width`}>
                <NativeSelect id={`${uid}-width`} value={String(d.width)} onChange={(e) => set({ width: Number(e.target.value) as WidgetWidth })}>
                  <option value="3">Quarter</option>
                  <option value="4">Third</option>
                  <option value="6">Half</option>
                  <option value="8">Two thirds</option>
                  <option value="12">Full</option>
                </NativeSelect>
              </Row>
            </div>
          </div>

          <div className="flex min-w-0 flex-col rounded-2xl border p-4" style={{ background: theme.card, borderColor: theme.cardBorder, color: theme.text }} data-testid="editor-preview">
            <p className="mb-2 text-sm font-semibold break-words">{title || "Preview"}</p>
            <div className="h-64 min-h-0">
              {previewError ? (
                <p className="flex h-full items-center justify-center text-center text-sm" style={{ color: theme.muted }} role="status">
                  {previewError}
                </p>
              ) : reason ? (
                <p className="flex h-full items-center justify-center text-center text-sm" style={{ color: theme.muted }} role="status">
                  {reason}
                </p>
              ) : result ? (
                <ChartBody chart={d.chart} result={result} theme={theme} />
              ) : (
                <div className="h-full animate-pulse rounded-xl" style={{ background: theme.grid, opacity: 0.5 }} role="status" aria-label="Calculating preview" />
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} disabled={!query || !title.trim() || Boolean(preview && !preview.ok)}>
            {widget ? "Save changes" : "Add to dashboard"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
