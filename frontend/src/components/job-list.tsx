import { CheckCircle2, CircleDashed, XCircle } from "lucide-react";
import type { Job } from "@/lib/api";
import { fmtDate } from "@/lib/utils";

const KIND: Record<string, string> = {
  upload: "Upload", clean: "Cleaning", analyze: "Analysis", insights: "Insights", export: "Export",
  cleaning_advice: "Cleaning advice",
};

export function JobList({ jobs, empty = "No activity yet." }: { jobs: Job[]; empty?: string }) {
  if (!jobs.length) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <ol className="space-y-3">
      {jobs.map((j) => (
        <li key={j.id} className="flex gap-3 text-sm">
          {j.status === "success" ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
          ) : j.status === "failed" ? (
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
          ) : (
            <CircleDashed className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          )}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-medium">{KIND[j.kind] ?? j.kind}</span>
              <span className="text-xs text-muted-foreground">{fmtDate(j.started_at, true)}</span>
              {typeof j.details?.duration_ms === "number" && (
                <span className="text-xs text-muted-foreground">· {j.details.duration_ms as number} ms</span>
              )}
            </div>
            <div className="truncate text-muted-foreground">{j.message || "—"}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}
