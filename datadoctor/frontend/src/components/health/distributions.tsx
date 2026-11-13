import type { ColumnProfile, Profile } from "@/lib/api";
import { SEVERITY_META } from "@/components/ui/severity-badge";
import { cn } from "@/lib/utils";
import { TYPE_META } from "./column-type";

const TYPE_COLORS: Record<string, string> = {
  integer: "var(--chart-1)", number: "var(--chart-1)", date: "var(--chart-3)", datetime: "var(--chart-3)",
  boolean: "var(--chart-4)", category: "var(--chart-2)", text: "var(--chart-5)", other: "var(--chart-8)", empty: "var(--chart-8)",
};

function Segments({ items, label }: { items: { key: string; label: string; count: number; color: string }[]; label: string }) {
  const total = items.reduce((a, b) => a + b.count, 0) || 1;
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full bg-muted" role="img" aria-label={`${label}: ${items.map((i) => `${i.count} ${i.label}`).join(", ")}`}>
        {items.map((i) => (
          <span key={i.key} style={{ width: `${(i.count / total) * 100}%`, background: i.color }} title={`${i.label}: ${i.count}`} />
        ))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {items.map((i) => (
          <li key={i.key} className="inline-flex items-center gap-1.5">
            <span className="size-2 rounded-full" style={{ background: i.color }} aria-hidden />
            {i.label} <span className="font-semibold text-foreground tabular-nums">{i.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Columns by detected data type. */
export function TypeDistribution({ columns }: { columns: ColumnProfile[] }) {
  const counts = new Map<string, number>();
  columns.forEach((c) => counts.set(c.type, (counts.get(c.type) ?? 0) + 1));
  const items = [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([type, count]) => ({ key: type, label: TYPE_META[type as keyof typeof TYPE_META]?.label ?? type, count, color: TYPE_COLORS[type] ?? "var(--chart-8)" }));
  return <Segments items={items} label="Columns by data type" />;
}

/** Column quality = share of values present × share matching the column's type. */
export function columnQuality(c: ColumnProfile): number {
  return (1 - c.missing_pct / 100) * (c.consistency ?? 0);
}

const QUALITY_BANDS = [
  { key: "excellent", label: "Excellent (95%+)", min: 0.95, color: "var(--success)" },
  { key: "good", label: "Good (80–95%)", min: 0.8, color: "var(--teal)" },
  { key: "attention", label: "Needs attention (50–80%)", min: 0.5, color: "var(--warning)" },
  { key: "poor", label: "Poor (under 50%)", min: -1, color: "var(--destructive)" },
];

export function QualityDistribution({ columns }: { columns: ColumnProfile[] }) {
  const items = QUALITY_BANDS.map((b, i) => ({
    key: b.key,
    label: b.label,
    color: b.color,
    count: columns.filter((c) => {
      const q = columnQuality(c);
      return q >= b.min && (i === 0 || q < QUALITY_BANDS[i - 1].min);
    }).length,
  })).filter((i) => i.count > 0);
  return <Segments items={items} label="Columns by quality" />;
}

export function SeverityBreakdown({ counts, className }: { counts: Profile["issue_counts"]; className?: string }) {
  const total = counts.high + counts.medium + counts.low;
  return (
    <div className={cn("space-y-2", className)} data-testid="issue-kpi">
      <p className="sr-only">
        {counts.high} high · {counts.medium} medium · {counts.low} low
      </p>
      <ul className="grid grid-cols-3 gap-2" aria-hidden>
        {(["high", "medium", "low"] as const).map((s) => {
          const meta = SEVERITY_META[s];
          return (
            <li key={s} className={cn("rounded-lg border px-3 py-2", meta.className)}>
              <p className="flex items-center gap-1 text-xs font-semibold">
                <meta.icon className="size-3.5" /> {meta.label}
              </p>
              <p className="text-xl font-bold tabular-nums">{counts[s]}</p>
            </li>
          );
        })}
      </ul>
      <p className="text-xs text-muted-foreground">{total === 0 ? "No issues found." : `${total} issue${total === 1 ? "" : "s"} in total.`}</p>
    </div>
  );
}
