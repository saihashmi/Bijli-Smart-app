import { ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";

/** Persistent reminder of SPEC default D2: single-user local mode, not for public hosting. */
export function LocalModeBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border border-warning/40 bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning-text",
        className,
      )}
      title="Local mode: single user on this computer. Not for public hosting. There are no user accounts yet."
    >
      <ShieldAlert className="size-3.5" aria-hidden />
      Local mode
      <span className="sr-only">: single user, not for public hosting</span>
    </span>
  );
}
