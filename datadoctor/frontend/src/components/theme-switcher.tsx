"use client";

import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
] as const;

/** Accessible segmented control (radio group) for light / dark / system theme. */
export function ThemeSwitcher({
  compact = false,
  onDark = false,
  className,
}: {
  compact?: boolean;
  /** Use colours suited to the navy sidebar. */
  onDark?: boolean;
  className?: string;
}) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const current = mounted ? theme : undefined;

  return (
    <div
      role="radiogroup"
      aria-label="Colour theme"
      className={cn(
        "inline-flex rounded-lg border p-0.5",
        onDark ? "border-sidebar-border bg-sidebar-accent" : "bg-muted",
        className,
      )}
    >
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const checked = current === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-label={label}
            title={label}
            onClick={() => setTheme(value)}
            className={cn(
              "inline-flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring",
              onDark ? "text-sidebar-foreground hover:text-sidebar-accent-foreground" : "text-muted-foreground hover:text-foreground",
              checked && (onDark ? "bg-sidebar-primary text-sidebar-primary-foreground" : "bg-card text-foreground shadow-sm"),
            )}
          >
            <Icon className="size-3.5" aria-hidden />
            {!compact && label}
          </button>
        );
      })}
    </div>
  );
}
