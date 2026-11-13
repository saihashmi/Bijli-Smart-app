/** Export Center API. Files are built on the server from the same figures the app shows. */
import { request } from "./api";

export type ExportType = "xlsx" | "pdf";
export type ExportJob = {
  id: string;
  type: ExportType;
  status: "running" | "done" | "failed" | "expired";
  created_at: string;
  completed_at: string | null;
  expires_at: string | null;
  error: string | null;
  details: { rows?: number; columns?: number; neutralised_cells?: number; pages?: number; charts?: number; size?: number } | null;
  file_name: string | null;
  download_url: string | null;
  link_valid_seconds: number;
};

export const exportsApi = {
  list: (id: string) => request<{ exports: ExportJob[] }>(`/sessions/${id}/exports`),
  create: (id: string, body: { type: ExportType; include_dashboard?: boolean; include_answers?: boolean }) =>
    request<ExportJob>(`/sessions/${id}/exports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  remove: (jobId: string) => request<void>(`/exports/${jobId}`, { method: "DELETE" }),
};
