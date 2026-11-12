import { AlertOctagon, AlertTriangle, Info } from "lucide-react";
import { cn } from "@/lib/utils";

export type Severity = "high" | "medium" | "low";

export const SEVERITY_META: Record<Severity, { label: string; icon: typeof Info; className: string }> = {
  high: { label: "High", icon: AlertOctagon, className: "border-destructive/40 bg-destructive/10 text-destructive-text" },
  medium: { label: "Medium", icon: AlertTriangle, className: "border-warning/40 bg-warning/10 text-warning-text" },
  low: { label: "Low", icon: Info, className: "border-border bg-muted text-muted-foreground" },
};

/** Severity is always shown with an icon AND a word, never colour alone. */
export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const meta = SEVERITY_META[severity];
  return (
    <span
      data-slot="badge"
      className={cn("inline-flex w-fit shrink-0 items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold", meta.className, className)}
    >
      <meta.icon className="size-3" aria-hidden />
      {meta.label}
      <span className="sr-only"> severity</span>
    </span>
  );
}
