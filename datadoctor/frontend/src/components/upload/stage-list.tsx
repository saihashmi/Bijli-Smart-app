import { Check, CircleDashed, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";

export type StageStatus = "pending" | "active" | "done" | "error";
export type Stage = { key: string; label: string; status: StageStatus; detail?: string };

/**
 * Real processing stages. Each stage maps to an actual request; a stage is "active" while that request is
 * in flight and "done" when it returns. No invented percentages: active stages show an indeterminate spinner.
 */
export function StageList({ stages, className }: { stages: Stage[]; className?: string }) {
  return (
    <ol className={cn("space-y-2.5", className)} aria-label="Processing stages" data-testid="stage-list">
      {stages.map((s) => (
        <li key={s.key} className="flex items-start gap-3 text-sm" data-stage={s.key} data-status={s.status}>
          <span
            className={cn(
              "mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border",
              s.status === "done" && "border-success/50 bg-success/15 text-success-text",
              s.status === "active" && "border-cyan/50 text-cyan-text",
              s.status === "error" && "border-destructive/50 bg-destructive/15 text-destructive-text",
              s.status === "pending" && "text-muted-foreground/60",
            )}
          >
            {s.status === "done" && <Check className="size-3" strokeWidth={3} aria-hidden />}
            {s.status === "active" && <Loader2 className="size-3 animate-spin" aria-hidden />}
            {s.status === "error" && <X className="size-3" strokeWidth={3} aria-hidden />}
            {s.status === "pending" && <CircleDashed className="size-3" aria-hidden />}
          </span>
          <span className={cn(s.status === "pending" && "text-muted-foreground", s.status === "active" && "font-medium")}>
            {s.label}
            <span className="sr-only">
              {s.status === "done" ? " (done)" : s.status === "active" ? " (in progress)" : s.status === "error" ? " (failed)" : " (waiting)"}
            </span>
            {s.detail && <span className="block text-xs text-muted-foreground">{s.detail}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}
