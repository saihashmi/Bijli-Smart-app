"use client";

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { api, ApiError, type Comparison } from "@/lib/api";
import { formatInteger } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

const PAGE = 50;

/** Original vs current data, aligned by original row; changed cells highlighted. */
export function CompareView({ sessionId, columns, version }: { sessionId: string; columns: string[]; version: number }) {
  const [selected, setSelected] = useState<string[]>(() => columns.slice(0, 6));
  const [changedOnly, setChangedOnly] = useState(true);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSelected((s) => {
      const kept = s.filter((c) => columns.includes(c));
      return kept.length ? kept : columns.slice(0, 6);
    });
    setOffset(0);
  }, [columns, version]);

  useEffect(() => {
    if (!selected.length) return;
    let alive = true;
    setError(null);
    api
      .compare(sessionId, { offset, limit: PAGE, changedOnly, columns: selected })
      .then((d) => alive && setData(d))
      .catch((e: unknown) => alive && setError(e instanceof ApiError ? e.message : "Could not compare."));
    return () => {
      alive = false;
    };
  }, [sessionId, selected, changedOnly, offset, version]);

  const toggle = (c: string, on: boolean) =>
    setSelected((s) => (on ? columns.filter((x) => s.includes(x) || x === c).slice(0, 20) : s.filter((x) => x !== c)));

  return (
    <div className="space-y-4" data-testid="compare-view">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <fieldset className="flex flex-wrap gap-x-4 gap-y-1.5" aria-label="Columns to compare">
          {columns.map((c) => (
            <label key={c} className="flex cursor-pointer items-center gap-1.5 text-sm">
              <Checkbox checked={selected.includes(c)} onCheckedChange={(v) => toggle(c, v === true)} aria-label={`Compare ${c}`} />
              {c}
            </label>
          ))}
        </fieldset>
        <div className="flex shrink-0 items-center gap-2">
          <Switch id="changed-only" checked={changedOnly} onCheckedChange={(v) => { setChangedOnly(v); setOffset(0); }} />
          <Label htmlFor="changed-only">Only changed rows</Label>
        </div>
      </div>

      {error && <p className="text-sm text-destructive-text">{error}</p>}
      {!data && !error && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Comparing…
        </p>
      )}
      {data && (
        <>
          <p className="text-sm text-muted-foreground">
            {formatInteger(data.changed_rows)} row(s) differ from the original in the selected columns
            {data.removed_rows > 0 && `, including ${formatInteger(data.removed_rows)} removed row(s)`}.
          </p>
          {data.rows.length === 0 ? (
            <p className="text-sm">No differences in the selected columns.</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full text-xs">
                <caption className="sr-only">Original and current values side by side</caption>
                <thead className="bg-muted text-muted-foreground">
                  <tr>
                    <th scope="col" className="px-2 py-1.5 text-left font-medium">
                      Row
                    </th>
                    {data.columns.map((c) => (
                      <th key={c.name} scope="col" className="px-2 py-1.5 text-left font-medium whitespace-nowrap">
                        {c.original && c.original !== c.name ? `${c.original} → ${c.name}` : c.name}
                        {!c.original && <Badge variant="secondary" className="ml-1">new</Badge>}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r) => (
                    <tr key={r.row} className={cn("border-t align-top", r.removed && "bg-destructive/5")}>
                      <th scope="row" className="px-2 py-1.5 text-left font-normal text-muted-foreground tabular-nums">
                        {r.row}
                        {r.removed && (
                          <Badge variant="destructive" className="ml-1">
                            Removed
                          </Badge>
                        )}
                      </th>
                      {r.cells.map((cell, i) => (
                        <td key={i} className={cn("px-2 py-1.5 font-mono whitespace-pre", cell.changed && !r.removed && "bg-warning/10")}>
                          {cell.new_column ? (
                            <span>{cell.after ?? "·"}</span>
                          ) : cell.changed && !r.removed ? (
                            <span className="flex flex-col">
                              <span className="text-destructive-text line-through decoration-destructive/40">{cell.before ?? "·"}</span>
                              <span className="text-success-text">{cell.after ?? "·"}</span>
                            </span>
                          ) : (
                            <span className={r.removed ? "text-muted-foreground" : ""}>{cell.before ?? "·"}</span>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {data.total > PAGE && (
            <div className="flex items-center gap-2 text-sm">
              <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE))}>
                <ChevronLeft /> Previous
              </Button>
              <span className="text-muted-foreground">
                {formatInteger(offset + 1)}–{formatInteger(Math.min(offset + PAGE, data.total))} of {formatInteger(data.total)}
              </span>
              <Button variant="outline" size="sm" disabled={offset + PAGE >= data.total} onClick={() => setOffset((o) => o + PAGE)}>
                Next <ChevronRight />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
