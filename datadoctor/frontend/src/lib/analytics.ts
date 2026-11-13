/** Types and API calls for the analytics engine. The browser never calculates figures; it only displays them. */
import { request } from "./api";

export type Agg = "count" | "sum" | "avg" | "min" | "max" | "median" | "distinct";
export type Grain = "day" | "week" | "month" | "quarter" | "year";
export type FieldKind = "number" | "date" | "boolean" | "category" | "text" | "other" | "empty";

export type Filter =
  | { op: "in" | "not_in"; column: string; values: string[]; include_missing?: boolean }
  | { op: "range"; column: string; min?: number | null; max?: number | null }
  | { op: "date_range"; column: string; start?: string | null; end?: string | null };

export type AggregateQuery = {
  kind: "aggregate";
  measure: { agg: Agg; column?: string | null };
  dimension?: { column: string; grain?: Grain | null } | null;
  series?: string | null;
  filters?: Filter[];
  sort?: { by: "value" | "label"; dir: "asc" | "desc" } | null;
  limit?: number | null;
  other?: boolean;
};
export type HistogramQuery = { kind: "histogram"; column: string; bins?: number; filters?: Filter[] };
export type ScatterQuery = { kind: "scatter"; x: string; y: string; filters?: Filter[] };
export type TableQuery = { kind: "table"; columns?: string[]; filters?: Filter[]; offset?: number; limit?: number };
export type Query = AggregateQuery | HistogramQuery | ScatterQuery | TableQuery;

export type ChartType = "kpi" | "bar" | "line" | "area" | "pie" | "donut" | "histogram" | "scatter" | "table";
export type WidgetWidth = 3 | 4 | 6 | 8 | 12;
export type Widget = { id: string; title: string; chart: ChartType; query: Query; width: WidgetWidth; reason?: string | null };
export type DashboardTheme = "midnight" | "executive" | "minimal";
export type Dashboard = { theme: DashboardTheme; filters: Filter[]; widgets: Widget[] };

export type Field = {
  name: string;
  kind: FieldKind;
  unique: number;
  present: number;
  missing: number;
  aggregations: Agg[];
  can_group: boolean;
  can_measure: boolean;
  sensitive: boolean;
  min?: number | string | null;
  max?: number | string | null;
  not_usable?: number;
  values?: string[];
};
export type FieldsResponse = {
  version: number;
  rows: number;
  fields: Field[];
  aggregations: { id: Agg; label: string }[];
  grains: Grain[];
  limits: { points: number; series: number; scatter_sample: number };
};

export type FilterInfo = { op: string; column: string; rows_matching: number; values_not_in_data?: string[] };
export type Meta = {
  rows_total: number;
  rows_after_filters: number;
  filters: FilterInfo[];
  measure_missing?: number;
  measure_not_usable?: number;
  dimension_missing?: number;
  dimension_not_dated?: number;
  groups_total?: number;
  other_groups?: number;
  other_included?: boolean;
  capped?: boolean;
  series_total?: number;
  series_other?: number;
  values_used?: number;
  pairs_used?: number;
  pairs_left_out?: number;
  sampled?: boolean;
  points_shown?: number;
};
export type AggRow = {
  key: string;
  label: string;
  value: number | string | null;
  n: number;
  rows: number;
  missing: boolean;
  other?: boolean;
  values?: Record<string, number | string | null>;
};
export type AggregateResult = {
  kind: "aggregate";
  measure: { agg: Agg; column: string | null; label: string };
  dimension: { column: string; kind: FieldKind; grain: Grain | null } | null;
  series: { column: string; names: string[] } | null;
  rows: AggRow[];
  total: { value: number | string | null; n: number };
  meta: Meta;
};
export type HistogramResult = {
  kind: "histogram";
  column: string;
  bins: { start: number; end: number; count: number }[];
  stats: { min: number; max: number; mean: number; median: number; q1: number; q3: number; std: number | null } | null;
  meta: Meta;
};
export type ScatterResult = { kind: "scatter"; x: string; y: string; points: [number, number][]; pearson_r: number | null; meta: Meta };
export type TableResult = {
  kind: "table";
  columns: string[];
  rows: string[][];
  row_numbers: number[];
  offset: number;
  total: number;
  meta: Meta;
};
export type QueryResult = AggregateResult | HistogramResult | ScatterResult | TableResult;
export type QueryOutcome = { ok: true; result: QueryResult } | { ok: false; error: { code: string; message: string } };

export type Recommendations = { kpis: Widget[]; charts: Widget[]; notes: string[] };
export type DashboardResponse = {
  saved: boolean;
  dashboard: Dashboard | null;
  updated_at: string | null;
  broken_widgets: { id: string; missing_columns: string[] }[];
};

const post = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const analytics = {
  fields: (id: string) => request<FieldsResponse>(`/sessions/${id}/analytics/fields`),
  run: (id: string, queries: Query[], filters: Filter[] = []) =>
    request<{ version: number; results: QueryOutcome[] }>(`/sessions/${id}/analytics/query`, post({ queries, filters })),
  recommendations: (id: string) => request<Recommendations>(`/sessions/${id}/analytics/recommendations`),
  dashboard: (id: string) => request<DashboardResponse>(`/sessions/${id}/dashboard`),
  saveDashboard: (id: string, dashboard: Dashboard) =>
    request<DashboardResponse>(`/sessions/${id}/dashboard`, { ...post(dashboard), method: "PUT" }),
  deleteDashboard: (id: string) => request<void>(`/sessions/${id}/dashboard`, { method: "DELETE" }),
};

export const AGG_LABEL: Record<Agg, string> = {
  count: "Count",
  sum: "Sum",
  avg: "Average",
  min: "Minimum",
  max: "Maximum",
  median: "Median",
  distinct: "Distinct count",
};

export const CHART_LABEL: Record<ChartType, string> = {
  kpi: "KPI card",
  bar: "Bar",
  line: "Line",
  area: "Area",
  pie: "Pie",
  donut: "Donut",
  histogram: "Histogram",
  scatter: "Scatter",
  table: "Table",
};

/** Plain-language notes about rows that were left out of a result. Empty when nothing was left out. */
export function exclusionNotes(result: QueryResult): string[] {
  const m = result.meta;
  const notes: string[] = [];
  const n = (x: number) => x.toLocaleString("en-US");
  const column =
    result.kind === "aggregate" ? result.measure.column : result.kind === "histogram" ? result.column : null;
  if (m.rows_after_filters < m.rows_total) notes.push(`Filters keep ${n(m.rows_after_filters)} of ${n(m.rows_total)} rows.`);
  if (m.measure_missing) notes.push(`${n(m.measure_missing)} rows have no value in “${column}” and are not counted as zero.`);
  if (m.measure_not_usable) notes.push(`${n(m.measure_not_usable)} values in “${column}” are not numbers and are left out.`);
  if (result.kind === "aggregate" && result.dimension) {
    if (m.dimension_not_dated)
      notes.push(
        `${n(m.dimension_not_dated)} rows have a date in “${result.dimension.column}” that is unclear or impossible, so they are in no period.`,
      );
    if (m.dimension_missing && result.dimension.kind === "date")
      notes.push(`${n(m.dimension_missing)} rows have no date in “${result.dimension.column}”.`);
    if (m.other_groups && m.other_included) notes.push(`${n(m.other_groups)} smaller groups are combined as “Other”.`);
    if (m.other_groups && m.other_included === false) notes.push(`${n(m.other_groups)} smaller groups are not shown.`);
    if (m.series_other) notes.push(`${n(m.series_other)} smaller series are combined as “Other”.`);
  }
  if (result.kind === "scatter") {
    if (m.pairs_left_out) notes.push(`${n(m.pairs_left_out)} rows lack a number in one of the two columns and are left out.`);
    if (m.sampled) notes.push(`Showing a random sample of ${n(m.points_shown ?? 0)} of ${n(m.pairs_used ?? 0)} points. The correlation uses all of them.`);
  }
  return notes;
}
