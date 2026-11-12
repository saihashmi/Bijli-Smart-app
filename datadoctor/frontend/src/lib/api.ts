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

export type Health = {
  status: "ok" | "degraded";
  version: string;
  ai_configured: boolean;
  checks: Record<string, "ok" | "error">;
};

// ---------- endpoints ----------
export const api = {
  health: () => request<Health>("/health"),
  settings: () => request<SettingsResponse>("/settings"),
  updateSettings: (patch: Partial<Preferences>) => request<SettingsResponse>("/settings", json("PUT", patch)),
  deleteAllData: () => request<{ datasets_deleted: number }>("/workspace/data", { method: "DELETE" }),
};
