import type { ColumnProfile } from "@/lib/api";
import { formatInteger } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Share of missing values per column (only columns that have any), largest first. */
export function MissingChart({ columns }: { columns: ColumnProfile[] }) {
  const rows = columns.filter((c) => c.missing > 0).sort((a, b) => b.missing_pct - a.missing_pct);
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">No missing values in any column.</p>;
  return (
    <figure>
      <figcaption className="sr-only">Missing values by column</figcaption>
      <ul className="space-y-2.5" data-testid="missing-chart">
        {rows.map((c) => (
          <li key={c.name} className="grid grid-cols-[minmax(6rem,12rem)_1fr_auto] items-center gap-3 text-sm">
            <span className="truncate font-medium" title={c.name}>
              {c.name}
            </span>
            <span className="h-3 rounded-full bg-muted" aria-hidden>
              <span
                className={cn(
                  "block h-3 rounded-full",
                  c.missing_pct > 20 ? "bg-destructive" : c.missing_pct >= 5 ? "bg-warning" : "bg-teal",
                )}
                style={{ width: `${Math.max(1, c.missing_pct)}%` }}
              />
            </span>
            <span className="text-right text-xs text-muted-foreground tabular-nums">
              {c.missing_pct}% · {formatInteger(c.missing)}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted-foreground">
        Bars: red above 20%, amber 5–20%, teal below 5%. Missing includes empty cells, spaces only, placeholders such as
        “N/A” and Excel errors.
      </p>
    </figure>
  );
}
