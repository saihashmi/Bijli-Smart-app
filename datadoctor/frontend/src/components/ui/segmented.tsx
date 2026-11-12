"use client";

import { cn } from "@/lib/utils";

export type SegmentedOption<T extends string> = { value: T; label: React.ReactNode; ariaLabel?: string };

/** Accessible segmented control (radio group semantics). */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  className,
  size = "md",
}: {
  value: T;
  onChange: (v: T) => void;
  options: SegmentedOption<T>[];
  label: string;
  className?: string;
  size?: "sm" | "md";
}) {
  return (
    <div role="radiogroup" aria-label={label} className={cn("inline-flex w-fit flex-wrap rounded-lg border bg-muted p-0.5", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          aria-label={o.ariaLabel}
          onClick={() => onChange(o.value)}
          className={cn(
            "inline-flex cursor-pointer items-center gap-1.5 rounded-md font-medium text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
            size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1 text-sm",
            value === o.value && "bg-card text-foreground shadow-sm",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
