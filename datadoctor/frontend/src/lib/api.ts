// Typed client for the DataDoctor API. All requests go to /api on the same origin (proxied to FastAPI).

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public errorId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Envelope = { error?: { code?: string; message?: string; id?: string } };

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { cache: "no-store", credentials: "same-origin", ...init });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Cannot reach the DataDoctor server. Is it running?");
  }
  if (!res.ok) {
    let body: Envelope = {};
    try {
      body = (await res.json()) as Envelope;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(
      res.status,
      body.error?.code ?? "HTTP_ERROR",
      body.error?.message ?? `Request failed (${res.status}).`,
      body.error?.id,
    );
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

// ---------- types ----------
export type DateDisplay = "DD/MM/YYYY" | "MM/DD/YYYY" | "YYYY-MM-DD";

export type Preferences = {
  display_timezone: string;
  date_display: DateDisplay;
  ai_share_column_names: boolean;
};

export type SystemInfo = {
  version: string;
  local_mode: boolean;
  retention_days: number;
  max_upload_mb: number;
  max_rows: number;
  max_columns: number;
  max_cells: number;
  process_timeout_s: number;
  ai_configured: boolean;
  ai_provider: string | null;
  ai_model: string | null;
};

export type SettingsResponse = { preferences: Preferences; system: SystemInfo };

export type ServerHealth = {
  status: "ok" | "degraded";
  version: string;
  ai_configured: boolean;
  checks: Record<string, "ok" | "error">;
};

export type Sheet = {
  index: number;
  name: string;
  visibility: "visible" | "hidden" | "very_hidden";
  rows: number;
  columns: number;
  formula_cells_without_cache: number;
  kind: string;
  selectable: boolean;
  problem: string | null;
};

export type CsvInfo = { encoding: string; delimiter: string; delimiter_label: string; replaced_characters: number };

export type SessionBrief = {
  id: string;
  sheet_index: number | null;
  sheet_name: string | null;
  header_row: number;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Dataset = {
  id: string;
  original_filename: string;
  file_type: "xlsx" | "xls" | "csv";
  file_size: number;
  uploaded_at: string;
  expires_at: string;
  status: string;
  sheets: Sheet[];
  csv: CsvInfo | null;
  warnings: string[];
  sessions: SessionBrief[];
};

export type Peek = { sheet_index: number; rows: string[][]; total_rows: number; total_columns: number; truncated_columns: boolean };

export type HeaderChange = { position: number; original: string; new: string; reason: "blank" | "duplicate" | "whitespace" };

export type AnalysisSession = {
  id: string;
  dataset_id: string;
  original_filename: string;
  file_type: string;
  file_size: number;
  sheet_index: number | null;
  sheet_name: string | null;
  header_row: number;
  rows: number | null;
  columns: number | null;
  column_names: string[];
  header_changes: HeaderChange[];
  warnings: string[];
  version: number;
  status: string;
  created_at: string;
  updated_at: string;
  expires_at: string;
};

export type RowsPage = {
  view: string;
  version: number;
  offset: number;
  total: number;
  columns: string[];
  rows: (string | null)[][];
  row_numbers: number[];
};

export type OpField = {
  name: string;
  kind:
    | "column"
    | "columns"
    | "select"
    | "boolean"
    | "text"
    | "number"
    | "tokens"
    | "category_mapping"
    | "rename_mapping"
    | "column_order"
    | "date_interpretation";
  label: string;
  default?: unknown;
  options?: { value: string; label: string }[];
  optional?: boolean;
  help?: string;
  filter?: "text" | "number" | "date";
  show_if?: Record<string, unknown>;
};

export type OperationSpec = {
  id: string;
  title: string;
  group: string;
  description: string;
  fields: OpField[];
  always_destructive: boolean;
};

export type PreviewRow = {
  row: number;
  before: Record<string, string | null>;
  after: Record<string, string | null>;
  removed: boolean;
  /** Columns whose shown text is unchanged but whose stored type changed (text → number/date). */
  converted: string[];
};

export type OpPreview = {
  operation_type: string;
  title: string;
  parameters: Record<string, unknown>;
  destructive: boolean;
  affected_rows: number;
  rows_before: number;
  rows_after: number;
  removed_rows: number;
  added_columns: string[];
  removed_columns: string[];
  renamed: Record<string, string>;
  summary: string;
  warnings: string[];
  failure_count: number;
  failures: { row: number; column: string; value: string; reason: string }[];
  columns_before: string[];
  columns_after: string[];
  sample: PreviewRow[];
};

export type AppliedOperation = {
  id: string;
  sequence_number: number;
  operation_type: string;
  title: string;
  parameters: Record<string, unknown>;
  affected_rows: number;
  status: "active" | "undone";
  created_at: string;
  undone_at: string | null;
  summary: string | null;
};

export type TimelineEvent = {
  id: string;
  type: "apply" | "undo" | "reset" | "sensitive_columns" | string;
  details: Record<string, unknown>;
  created_at: string;
};

export type Timeline = { operations: AppliedOperation[]; events: TimelineEvent[]; current_version: number };

export type Comparison = {
  columns: { name: string; original: string | null }[];
  total: number;
  changed_rows: number;
  removed_rows: number;
  offset: number;
  version: number;
  rows: {
    row: number;
    removed: boolean;
    cells: { before: string | null; after: string | null; changed: boolean; new_column: boolean }[];
  }[];
};

export type CategoryGroup = { suggested: string; variants: { label: string; count: number }[] };

export type ColumnType = "integer" | "number" | "date" | "datetime" | "boolean" | "category" | "text" | "other" | "empty";

export type ColumnProfile = {
  name: string;
  rows: number;
  non_missing: number;
  missing: number;
  missing_pct: number;
  missing_kinds: { empty: number; whitespace_only: number; null_token: number; excel_error: number };
  class_counts: Record<string, number>;
  whitespace_issues: number;
  repeated_spaces: number;
  type: ColumnType;
  family: string;
  consistency: number | null;
  mixed: boolean;
  family_counts?: Record<string, number>;
  unique: number;
  unique_pct?: number;
  examples: { row: number; value: string }[];
  numeric?: {
    count: number; min: number | null; max: number | null; mean: number | null; median: number | null; std: number | null;
    q1: number | null; q3: number | null; negatives: number; zeros: number; stored_as_text: number;
    histogram: { start: number; end: number; count: number }[]; excel_serial_candidates: number;
  };
  date?: {
    native: number; text: number; formats: Record<string, number>; evidence: Record<string, number>; ambiguous: number;
    invalid: number; resolved: number; min: string | null; max: string | null; future: number; range_note: string | null;
  };
  boolean?: { true: number; false: number };
  text?: { min_length: number; max_length: number };
  top_values?: { value: string; count: number; pct: number }[];
  top_values_other?: number;
};

export type Severity = "high" | "medium" | "low";

export type Issue = {
  id: string;
  code: string;
  title: string;
  column: string | null;
  affected_rows: number;
  affected_pct: number;
  severity: Severity;
  description: string;
  examples: { row: number | null; value: string }[];
  suggested_action: { operation: string | null; label: string };
  details: Record<string, unknown>;
};

export type HealthComponent = { key: string; value: number; weight: number; points: number; explanation: string };

export type Health = {
  score: number;
  band: "Excellent" | "Good" | "Needs attention" | "Poor";
  components: HealthComponent[];
  formula: string;
  limitations: string[];
};

export type Profile = {
  session_id: string;
  version: number;
  calculated_at: string;
  rows: number;
  columns: number;
  total_cells: number;
  missing_cells: number;
  missing_pct: number;
  duplicate_rows: number;
  empty_rows: number;
  empty_columns: number;
  column_profiles: ColumnProfile[];
  issues: Issue[];
  issue_counts: Record<Severity, number>;
  health: Health | null;
  sensitive_columns: string[];
};

/** Upload with real progress events (fetch has no upload progress). Resolves with the created dataset. */
export function uploadFile(
  file: File,
  onProgress: (loaded: number, total: number) => void,
  signal?: AbortSignal,
): Promise<Dataset> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/uploads");
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded, e.total);
    };
    xhr.onload = () => {
      const body = xhr.response as (Dataset & Envelope) | null;
      if (xhr.status >= 200 && xhr.status < 300 && body) return resolve(body as Dataset);
      reject(
        new ApiError(
          xhr.status,
          body?.error?.code ?? "HTTP_ERROR",
          body?.error?.message ?? `Upload failed (${xhr.status}).`,
          body?.error?.id,
        ),
      );
    };
    xhr.onerror = () => reject(new ApiError(0, "NETWORK_ERROR", "The upload was interrupted. Check that the server is running."));
    xhr.onabort = () => reject(new ApiError(0, "ABORTED", "Upload cancelled."));
    signal?.addEventListener("abort", () => xhr.abort());
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

// ---------- endpoints ----------
export const api = {
  health: () => request<ServerHealth>("/health"),
  settings: () => request<SettingsResponse>("/settings"),
  updateSettings: (patch: Partial<Preferences>) => request<SettingsResponse>("/settings", json("PUT", patch)),
  deleteAllData: () => request<{ datasets_deleted: number }>("/workspace/data", { method: "DELETE" }),
  datasets: () => request<Dataset[]>("/datasets"),
  dataset: (id: string) => request<Dataset>(`/datasets/${id}`),
  deleteDataset: (id: string) => request<void>(`/datasets/${id}`, { method: "DELETE" }),
  peek: (id: string, sheet: number, rows = 15) => request<Peek>(`/datasets/${id}/sheets/${sheet}/peek?rows=${rows}`),
  createSession: (id: string, sheet_index: number, header_row: number) =>
    request<AnalysisSession>(`/datasets/${id}/sessions`, json("POST", { sheet_index, header_row })),
  sessions: () => request<AnalysisSession[]>("/sessions"),
  session: (id: string) => request<AnalysisSession>(`/sessions/${id}`),
  operations: () => request<OperationSpec[]>("/cleaning/operations"),
  previewOp: (id: string, operation_type: string, parameters: Record<string, unknown>) =>
    request<OpPreview>(`/sessions/${id}/cleaning/preview`, json("POST", { operation_type, parameters })),
  applyOp: (id: string, operation_type: string, parameters: Record<string, unknown>, confirm: boolean) =>
    request<{ operation: AppliedOperation; result: OpPreview; session: AnalysisSession }>(
      `/sessions/${id}/cleaning/apply`,
      json("POST", { operation_type, parameters, confirm }),
    ),
  categorySuggestions: (id: string, column: string) =>
    request<{ column: string; groups: CategoryGroup[] }>(
      `/sessions/${id}/cleaning/category-suggestions?column=${encodeURIComponent(column)}`,
    ),
  history: (id: string) => request<AppliedOperation[]>(`/sessions/${id}/history`),
  timeline: (id: string) => request<Timeline>(`/sessions/${id}/timeline`),
  undo: (id: string) => request<{ undone: number[]; session: AnalysisSession }>(`/sessions/${id}/cleaning/undo`, { method: "POST" }),
  reset: (id: string) =>
    request<{ undone: number[]; session: AnalysisSession }>(`/sessions/${id}/cleaning/reset`, json("POST", { confirm: true })),
  compare: (id: string, opts: { offset: number; limit: number; changedOnly: boolean; columns: string[] }) => {
    const q = new URLSearchParams({ offset: String(opts.offset), limit: String(opts.limit), changed_only: String(opts.changedOnly) });
    opts.columns.forEach((c) => q.append("columns", c));
    return request<Comparison>(`/sessions/${id}/compare?${q}`);
  },
  rows: (id: string, offset: number, limit: number, view: "current" | "original" = "current") =>
    request<RowsPage>(`/sessions/${id}/rows?view=${view}&offset=${offset}&limit=${limit}`),
  profile: (id: string) => request<Profile>(`/sessions/${id}/profile`),
  setSensitive: (id: string, columns: string[]) =>
    request<{ sensitive_columns: string[] }>(`/sessions/${id}/sensitive-columns`, json("PUT", { columns })),
  deleteSession: (id: string) => request<void>(`/sessions/${id}`, { method: "DELETE" }),
};
