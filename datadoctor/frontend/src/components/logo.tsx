import { Activity } from "lucide-react";
import { cn } from "@/lib/utils";

export function Logo({ className, inverted = false }: { className?: string; inverted?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold tracking-tight", className)}>
      <span className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground shadow-sm" aria-hidden>
        <Activity className="size-4.5" strokeWidth={2.5} />
      </span>
      <span className={cn(inverted ? "text-white" : "text-navy dark:text-foreground")}>
        DataDoctor <span className={inverted ? "text-teal" : "text-teal-text"}>AI</span>
      </span>
    </span>
  );
}
