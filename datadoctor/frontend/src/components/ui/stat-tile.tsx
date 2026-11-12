import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function StatTile({
  icon: Icon,
  label,
  value,
  sub,
  tone = "default",
  className,
  ...props
}: {
  icon: LucideIcon;
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: "default" | "good" | "warn" | "bad";
} & React.ComponentProps<"div">) {
  const toneClass = { default: "text-primary", good: "text-success-text", warn: "text-warning-text", bad: "text-destructive-text" }[tone];
  return (
    <div
      className={cn("rounded-xl border bg-card p-4 shadow-xs transition-shadow duration-200 hover:shadow-md", className)}
      {...props}
    >
      <p className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <span className={cn("grid size-6 place-items-center rounded-md bg-muted", toneClass)}>
          <Icon className="size-3.5" aria-hidden />
        </span>
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}
