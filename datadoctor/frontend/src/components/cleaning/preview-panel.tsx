"use client";

import { AlertTriangle, ArrowRight, Info } from "lucide-react";
import type { OpPreview } from "@/lib/api";
import { formatInteger } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

function Value({ v, tone }: { v: string | null | undefined; tone?: "old" | "new" }) {
  if (v === undefined) return <span className="text-muted-foreground">–</span>;
  if (v === null) return <span className="text-muted-foreground italic">empty</span>;
  return (
    <span
      className={cn(
        "font-mono whitespace-pre",
        tone === "old" && "text-destructive-text line-through decoration-destructive/40",
        tone === "new" && "text-success-text",
      )}
    >
      {v === "" ? "“”" : v}
    </span>
  );
}

/** Before → after comparison for the first affected rows, computed from the full data by the server. */
export function PreviewPanel({ preview }: { preview: OpPreview }) {
  const cols = Array.from(new Set([...preview.columns_before, ...preview.columns_after]));
  const renamedBack = Object.fromEntries(Object.entries(preview.renamed).map(([a, b]) => [b, a]));
  const pct = preview.rows_before ? (preview.affected_rows / preview.rows_before) * 100 : 0;

  return (
    <div className="space-y-4" data-testid="op-preview">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={preview.affected_rows ? (preview.destructive ? "destructive" : "default") : "secondary"}>
          {formatInteger(preview.affected_rows)} row{preview.affected_rows === 1 ? "" : "s"} affected
        </Badge>
        <span className="text-sm text-muted-foreground">
          {pct ? `${pct.toFixed(pct < 1 ? 2 : 1)}% of ${formatInteger(preview.rows_before)} rows` : `of ${formatInteger(preview.rows_before)} rows`}
          {preview.removed_rows > 0 && ` · ${formatInteger(preview.rows_after)} rows will remain`}
        </span>
      </div>
      <p className="text-sm" data-testid="preview-summary">
        {preview.summary}
      </p>
      {preview.added_columns.length > 0 && (
        <p className="text-sm text-muted-foreground">New column(s): {preview.added_columns.map((c) => `“${c}”`).join(", ")}</p>
      )}
      {preview.warnings.map((w) => (
        <Alert key={w} variant="warning">
          <Info aria-hidden />
          <AlertDescription>{w}</AlertDescription>
        </Alert>
      ))}

      {preview.sample.length > 0 && cols.length > 0 && (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-xs">
            <caption className="sr-only">Before and after for the first affected rows</caption>
            <thead className="bg-muted text-muted-foreground">
              <tr>
                <th scope="col" className="px-2 py-1.5 text-left font-medium">
                  Row
                </th>
                {cols.map((c) => (
                  <th key={c} scope="col" className="px-2 py-1.5 text-left font-medium whitespace-nowrap">
                    {renamedBack[c] ? (
                      <>
                        {renamedBack[c]} <ArrowRight className="inline size-3" /> {c}
                      </>
                    ) : (
                      c
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.sample.map((r) => (
                <tr key={r.row} className="border-t align-top">
                  <th scope="row" className="px-2 py-1.5 text-left font-normal text-muted-foreground tabular-nums">
                    {r.row}
                    {r.removed && (
                      <Badge variant="destructive" className="ml-1">
                        Removed
                      </Badge>
                    )}
                  </th>
                  {cols.map((c) => {
                    const src = renamedBack[c] ?? c;
                    const before = src in r.before ? r.before[src] : undefined;
                    const after = c in r.after ? r.after[c] : undefined;
                    const changed = !r.removed && before !== after && !(c in r.after && !(src in r.before)) ? true : false;
                    return (
                      <td key={c} className="px-2 py-1.5">
                        {r.removed ? (
                          <Value v={before} />
                        ) : !(src in r.before) ? (
                          <Value v={after} tone="new" />
                        ) : r.converted?.includes(c) ? (
                          <span className="flex flex-wrap items-center gap-1">
                            <Value v={after} tone="new" />
                            <Badge variant="success">converted</Badge>
                          </span>
                        ) : changed ? (
                          <span className="flex flex-wrap items-center gap-1">
                            <Value v={before} tone="old" /> <ArrowRight className="size-3 text-muted-foreground" aria-label="becomes" />{" "}
                            <Value v={after} tone="new" />
                          </span>
                        ) : (
                          <Value v={before} />
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          {preview.affected_rows > preview.sample.length && (
            <p className="border-t px-2 py-1.5 text-xs text-muted-foreground">
              Showing {preview.sample.length} of {formatInteger(preview.affected_rows)} affected rows.
            </p>
          )}
        </div>
      )}

      {preview.failure_count > 0 && (
        <details className="rounded-lg border border-warning/40 bg-warning/5 px-3 py-2 text-sm" data-testid="failure-report">
          <summary className="flex cursor-pointer items-center gap-2 font-medium">
            <AlertTriangle className="size-4 text-warning-text" aria-hidden />
            {formatInteger(preview.failure_count)} value(s) could not be converted
          </summary>
          <table className="mt-2 w-full text-xs">
            <thead className="text-muted-foreground">
              <tr>
                <th className="text-left font-medium">Row</th>
                <th className="text-left font-medium">Column</th>
                <th className="text-left font-medium">Value</th>
                <th className="text-left font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {preview.failures.map((f, i) => (
                <tr key={i} className="border-t">
                  <td className="py-1 tabular-nums">{f.row}</td>
                  <td className="py-1">{f.column}</td>
                  <td className="py-1 font-mono">{f.value}</td>
                  <td className="py-1">{f.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {preview.failure_count > preview.failures.length && (
            <p className="mt-1 text-xs text-muted-foreground">First {preview.failures.length} shown.</p>
          )}
        </details>
      )}
    </div>
  );
}
