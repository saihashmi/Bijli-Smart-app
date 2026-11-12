// Typed client for the FastAPI backend. Requests go to /api on the same origin (proxied by Next).

export type Mapping = {
  timestamp: string | null;
  consumption: string | null;
  cost: string | null;
  category: string | null;
  dayfirst: boolean;
  confidence?: Record<string, number>;
};

export type DatasetSettings = {
  currency: string;
  tariff_per_kwh: number | null;
  peak_start_hour: number;
  peak_end_hour: number;
  reduction_target_pct: number;
};

export type CleaningLogEntry = {
  action: string; title: string; rows_before: number; rows_after: number; values_changed: number; detail: string;
};

export type Dataset = {
  id: string; name: string; original_filename: string; file_type: string; status: "uploaded" | "cleaned";
  rows_raw: number; rows_clean: number | null; columns: string[]; mapping: Mapping; settings: DatasetSettings;
  cleaning_log: CleaningLogEntry[]; created_at: string; updated_at: string;
};

export type Job = {
  id: number; dataset_id: string | null; kind: string; status: "running" | "success" | "failed";
  message: string; details: Record<string, unknown>; started_at: string; finished_at: string | null;
};

export type Suggestion = {
  id: string; title: string; group: string | null; affected_rows: number; reason: string; recommended: boolean;
};

export type ColumnProfile = {
  name: string; role: string | null; kind: "datetime" | "numeric" | "text"; missing: number; missing_pct: number;
  unique: number; sample: string[]; unparseable?: number; negatives?: number; min?: number | string | null;
  max?: number | string | null; mean?: number | null; whitespace_issues?: number;
};

export type Profile = {
  rows: number; columns_count: number; empty_rows: number; duplicate_rows: number;
  columns: ColumnProfile[]; suggestions: Suggestion[];
};

export type Removed = { text: string; reason: string };

export type CleaningAdvice = {
  source: "groq" | "rules"; model?: string; overview: string;
  actions: { id: string; advice: string; apply: boolean }[]; removed: Removed[]; ai_error?: string;
};

export type Fact = {
  id: string; category: string; text: string; values: Record<string, number | null>;
  severity: "info" | "warning" | "positive";
};

export type Analysis = {
  empty: boolean; message?: string; data_stage: "raw" | "cleaned";
  summary: {
    records: number; start: string; end: string; span_days: number; days_with_data: number; granularity: string;
    total_kwh: number; avg_daily_kwh: number | null; total_cost: number | null; effective_rate: number | null;
    cost_source: "file" | "tariff" | null; currency: string;
    peak_day?: { date: string; kwh: number }; lowest_day?: { date: string; kwh: number };
    peak_month?: { month: string; kwh: number };
  };
  daily: { date: string; kwh: number; cost?: number }[];
  monthly: { month: string; kwh: number; change_pct: number | null; cost?: number }[];
  weekday: { day: string; avg_kwh: number }[] | null;
  hourly: { hour: number; avg_kwh: number }[] | null;
  peak_hours: { window: string; hours: number; kwh: number; share_pct: number; even_share_pct: number } | null;
  baseload: { kw: number; kwh: number; share_pct: number; hours_observed: number } | null;
  categories: { category: string; kwh: number; share_pct: number; cost?: number }[] | null;
  trend: { unit: string; slope_kwh_per_period: number; first_half_avg: number; second_half_avg: number;
    change_pct: number | null; direction: "rising" | "falling" | "stable" } | null;
  anomalies: { date: string; kwh: number; typical_kwh: number; deviation_pct: number; direction: "high" | "low" }[];
  savings: { id: string; title: string; kwh: number; cost: number | null; basis: string }[];
  settings: DatasetSettings;
  facts: Fact[];
};

export type Insights = {
  source: "groq" | "rules"; model?: string; summary: string; data_stage?: string; ai_error?: string;
  insights: { title: string; explanation: string; fact_ids: string[]; severity?: string }[];
  recommendations: { action: string; why: string; fact_ids: string[] }[];
  removed: Removed[]; facts: Fact[];
};

export type Preview = { stage: string; total: number; offset: number; columns: string[]; rows: unknown[][] };

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { cache: "no-store", ...init });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* keep status text */
    }
    throw new ApiError(res.status, msg || `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (body: unknown, method = "POST"): RequestInit => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

export const api = {
  health: () => request<{ status: string; ai_enabled: boolean; ai_model: string | null }>("/health"),
  datasets: () => request<Dataset[]>("/datasets"),
  dataset: (id: string) => request<Dataset>(`/datasets/${id}`),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<Dataset>("/datasets", { method: "POST", body: fd });
  },
  configure: (id: string, body: { mapping?: Partial<Mapping>; settings?: DatasetSettings; name?: string }) =>
    request<Dataset>(`/datasets/${id}`, json(body, "PATCH")),
  remove: (id: string) => request<void>(`/datasets/${id}`, { method: "DELETE" }),
  profile: (id: string) => request<Profile>(`/datasets/${id}/profile`),
  cleaningAdvice: (id: string) => request<CleaningAdvice>(`/datasets/${id}/cleaning-advice`, { method: "POST" }),
  clean: (id: string, actions: string[]) => request<Dataset>(`/datasets/${id}/clean`, json({ actions })),
  resetClean: (id: string) => request<Dataset>(`/datasets/${id}/clean`, { method: "DELETE" }),
  preview: (id: string, stage: "raw" | "clean", offset = 0, limit = 50) =>
    request<Preview>(`/datasets/${id}/preview?stage=${stage}&offset=${offset}&limit=${limit}`),
  analysis: (id: string) => request<Analysis>(`/datasets/${id}/analysis`),
  insights: (id: string, useAi = true) => request<Insights>(`/datasets/${id}/insights?use_ai=${useAi}`, { method: "POST" }),
  exportUrl: (id: string, format: "xlsx" | "pdf", useAi = false) => `/api/datasets/${id}/export?format=${format}&use_ai=${useAi}`,
  jobs: (datasetId?: string) => request<Job[]>(datasetId ? `/datasets/${datasetId}/jobs` : "/jobs?limit=20"),
};
