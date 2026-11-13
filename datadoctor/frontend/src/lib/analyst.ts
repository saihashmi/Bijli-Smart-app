/** AI Analyst types and API calls. Answers are computed on the server by allowlisted operations only. */
import type { ChartType, QueryResult } from "./analytics";
import { request } from "./api";

export type FormRole = "any" | "group" | "date" | "number" | "agg" | "grain" | "order" | "which" | "values" | "int" | "columns";
export type FormField = { name: string; role: FormRole; optional?: boolean };
export type Operation = { id: string; title: string; example: string; fields: FormField[] };
export type Catalogue = {
  operations: Operation[];
  limitations: string[];
  ai: { configured: boolean; provider: string | null; model: string | null };
};
export type Suggestion = { question: string; operation: string; params: Record<string, unknown> };
export type Answer = {
  operation: string;
  params: Record<string, unknown>;
  title: string;
  answer: string;
  table: { columns: string[]; rows: string[][] } | null;
  chart: { chart: ChartType; result: QueryResult } | null;
  notes: string[];
};
export type AskResponse = {
  id: string;
  status: "answered" | "cannot_answer";
  question: string;
  interpreter: "local" | "groq" | "guided";
  answer: Answer | null;
  explanation: { text: string; provider: string; model: string; status: "verified" } | null;
  notices: string[];
  alternatives: Suggestion[];
  message: string | null;
};
export type Interaction = {
  id: string;
  question: string;
  operation: string | null;
  params: Record<string, unknown>;
  summary: string;
  provider: string;
  explanation_status: string;
  created_at: string;
};

const post = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const analyst = {
  catalogue: () => request<Catalogue>("/analyst/operations"),
  suggestions: (id: string) => request<{ suggestions: Suggestion[] }>(`/sessions/${id}/analyst/suggestions`),
  ask: (id: string, body: { question?: string; operation?: string; params?: Record<string, unknown> }) =>
    request<AskResponse>(`/sessions/${id}/analyst/ask`, post(body)),
  history: (id: string) => request<{ interactions: Interaction[] }>(`/sessions/${id}/analyst/history`),
};

const PARAM_LABEL: Record<string, string> = {
  measure: "Column",
  agg: "Calculation",
  group_by: "Group by",
  order: "Order",
  top_n: "Show top",
  date_col: "Date column",
  grain: "Period",
  which: "Find",
  values: "Values",
  column: "Column",
  x: "First column",
  y: "Second column",
  key_columns: "Key columns",
  bins: "Bars",
  codes: "Issue codes",
  filters: "Filters",
};
const VALUE_LABEL: Record<string, string> = {
  sum: "total",
  avg: "average",
  count: "count",
  min: "minimum",
  max: "maximum",
  median: "median",
  distinct: "distinct count",
  desc: "largest first",
  asc: "smallest first",
};

export const paramLabel = (name: string) => PARAM_LABEL[name] ?? name;

/** The settings of a calculation as short readable pairs, so the user can check how a question was understood. */
export function describeParams(params: Record<string, unknown>): { label: string; value: string }[] {
  const out: { label: string; value: string }[] = [];
  for (const [key, raw] of Object.entries(params)) {
    if (raw === null || raw === undefined || (Array.isArray(raw) && raw.length === 0)) continue;
    let value: string;
    if (key === "which") value = raw === "max" ? "highest" : "lowest";
    else if (Array.isArray(raw)) value = key === "filters" ? `${raw.length} applied` : raw.join(", ");
    else value = VALUE_LABEL[String(raw)] ?? String(raw);
    out.push({ label: paramLabel(key), value });
  }
  return out;
}
