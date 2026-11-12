import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  ...props
}: { icon: LucideIcon; title: string; description?: React.ReactNode; action?: React.ReactNode } & React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex flex-col items-center gap-3 rounded-2xl border border-dashed bg-card/50 px-6 py-12 text-center", className)}
      {...props}
    >
      <span className="grid size-14 place-items-center rounded-2xl bg-accent text-primary dark:text-link">
        <Icon className="size-7" aria-hidden />
      </span>
      <div className="space-y-1">
        <p className="text-lg font-semibold">{title}</p>
        {description && <p className="mx-auto max-w-md text-sm text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  );
}
