"use client";

import { Loader2, ShieldCheck, ShieldOff } from "lucide-react";
import type { ColumnProfile } from "@/lib/api";
import { formatInteger } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TypeLabel } from "./column-type";

const num = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined ? "–" : new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(v);

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="truncate font-medium tabular-nums">{value}</dd>
    </div>
  );
}

function Histogram({ bins }: { bins: { start: number; end: number; count: number }[] }) {
  const max = Math.max(1, ...bins.map((b) => b.count));
  return (
    <figure>
      <div className="flex h-14 items-end gap-px" role="img" aria-label="Distribution of values">
        {bins.map((b, i) => (
          <div
            key={i}
            className="flex-1 rounded-t-sm bg-chart-1/70"
            style={{ height: `${Math.max(2, (b.count / max) * 100)}%` }}
            title={`${num(b.start)} – ${num(b.end)}: ${formatInteger(b.count)}`}
          />
        ))}
      </div>
      <figcaption className="mt-1 flex justify-between text-[11px] text-muted-foreground tabular-nums">
        <span>{num(bins[0]?.start)}</span>
        <span>{num(bins[bins.length - 1]?.end)}</span>
      </figcaption>
    </figure>
  );
}

function TopValues({ values, other }: { values: { value: string; count: number; pct: number }[]; other: number }) {
  return (
    <ul className="space-y-1.5" aria-label="Most frequent values">
      {values.slice(0, 5).map((v) => (
        <li key={v.value} className="text-xs">
          <div className="flex justify-between gap-2">
            <span className="truncate font-mono whitespace-pre" title={v.value}>
              {v.value}
            </span>
            <span className="shrink-0 text-muted-foreground tabular-nums">
              {formatInteger(v.count)} · {v.pct}%
            </span>
          </div>
          <div className="mt-0.5 h-1.5 rounded-full bg-muted">
            <div className="h-1.5 rounded-full bg-chart-2" style={{ width: `${v.pct}%` }} />
          </div>
        </li>
      ))}
      {other > 0 && values.length > 5 && <li className="text-xs text-muted-foreground">+ {formatInteger(other)} more values</li>}
    </ul>
  );
}

export function ColumnCard({
  col,
  sensitive,
  busy,
  onToggleSensitive,
}: {
  col: ColumnProfile;
  sensitive: boolean;
  busy: boolean;
  onToggleSensitive: () => void;
}) {
  const notes: string[] = [];
  if (col.mixed && col.consistency !== null)
    notes.push(`${Math.round(col.consistency * 100)}% of values match the column type`);
  const n = (count: number, one: string, many: string) => `${formatInteger(count)} ${count === 1 ? one : many}`;
  if (col.numeric?.stored_as_text) notes.push(n(col.numeric.stored_as_text, "number stored as text", "numbers stored as text"));
  if (col.date?.ambiguous) notes.push(`${n(col.date.ambiguous, "ambiguous date", "ambiguous dates")} (DD/MM or MM/DD)`);
  if (col.date?.invalid) notes.push(n(col.date.invalid, "invalid date", "invalid dates"));
  if (col.whitespace_issues)
    notes.push(n(col.whitespace_issues, "value with extra spaces at the ends", "values with extra spaces at the ends"));
  if (col.missing_kinds.null_token)
    notes.push(n(col.missing_kinds.null_token, "placeholder value like “N/A”", "placeholder values like “N/A”"));

  return (
    <Card className="gap-3 py-4" data-testid="column-card">
      <CardHeader className="gap-1 px-4">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm break-all">{col.name}</CardTitle>
          <TypeLabel type={col.type} mixed={col.mixed} />
        </div>
        <button
          type="button"
          aria-pressed={sensitive}
          onClick={onToggleSensitive}
          disabled={busy}
          className={cn(
            "inline-flex w-fit cursor-pointer items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60",
            sensitive ? "border-primary/40 bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-muted",
          )}
          title={sensitive ? "Sensitive: never sent to AI features. Click to unmark." : "Mark as sensitive to keep it away from AI features"}
        >
          {busy ? <Loader2 className="size-3 animate-spin" /> : sensitive ? <ShieldCheck className="size-3" /> : <ShieldOff className="size-3" />}
          {sensitive ? "Sensitive" : "Not sensitive"}
          <span className="sr-only"> column {col.name}</span>
        </button>
      </CardHeader>
      <CardContent className="space-y-3 px-4 text-sm">
        <dl className="grid grid-cols-3 gap-2">
          <Stat
            label="Missing"
            value={<span className={cn(col.missing_pct >= 20 && "text-destructive-text", col.missing_pct >= 5 && col.missing_pct < 20 && "text-warning-text")}>{col.missing_pct}%</span>}
          />
          <Stat label="Unique" value={formatInteger(col.unique)} />
          <Stat label="Filled" value={formatInteger(col.non_missing)} />
        </dl>

        {col.numeric && (
          <>
            <dl className="grid grid-cols-3 gap-2">
              <Stat label="Min" value={num(col.numeric.min)} />
              <Stat label="Median" value={num(col.numeric.median)} />
              <Stat label="Max" value={num(col.numeric.max)} />
              <Stat label="Mean" value={num(col.numeric.mean)} />
              <Stat label="Std dev" value={num(col.numeric.std)} />
              <Stat label="Negative" value={formatInteger(col.numeric.negatives)} />
            </dl>
            {col.numeric.histogram.length > 1 && <Histogram bins={col.numeric.histogram} />}
          </>
        )}

        {col.date && (
          <dl className="grid grid-cols-2 gap-2">
            <Stat label="Earliest" value={col.date.min ?? "–"} />
            <Stat label="Latest" value={col.date.max ?? "–"} />
            <Stat label="Formats found" value={Object.keys(col.date.formats).length + (col.date.native ? 1 : 0)} />
            <Stat label="In the future" value={formatInteger(col.date.future)} />
          </dl>
        )}
        {col.date?.range_note && <p className="text-xs text-muted-foreground">{col.date.range_note}</p>}

        {col.boolean && (
          <dl className="grid grid-cols-2 gap-2">
            <Stat label="Yes / True" value={formatInteger(col.boolean.true)} />
            <Stat label="No / False" value={formatInteger(col.boolean.false)} />
          </dl>
        )}

        {col.top_values && col.top_values.length > 0 && !col.numeric && (
          <TopValues values={col.top_values} other={col.top_values_other ?? 0} />
        )}

        {notes.length > 0 && (
          <ul className="flex flex-wrap gap-1.5" aria-label="Observations">
            {notes.map((n) => (
              <li key={n}>
                <Badge variant="warning" className="whitespace-normal">
                  {n}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
