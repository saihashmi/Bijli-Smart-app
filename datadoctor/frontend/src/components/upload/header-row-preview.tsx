"use client";

import type { Peek } from "@/lib/api";
import { columnLetter } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";

/** Raw first rows of the sheet (values exactly as stored) with the chosen header row highlighted. */
export function HeaderRowPreview({ peek, headerRow, onHeaderRow }: { peek: Peek; headerRow: number; onHeaderRow: (r: number) => void }) {
  const width = Math.max(1, ...peek.rows.map((r) => r.length));
  const choices = peek.rows.map((_, i) => i).slice(0, Math.min(peek.rows.length, 20));

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <Label htmlFor="header-row">Column names are in</Label>
          <p className="text-xs text-muted-foreground">Rows above it (titles, notes) will be skipped. Nothing in your file is changed.</p>
        </div>
        <div className="w-full sm:w-44">
          <NativeSelect id="header-row" value={headerRow} onChange={(e) => onHeaderRow(Number(e.target.value))}>
            {choices.map((i) => (
              <option key={i} value={i}>
                Row {i + 1}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border" data-testid="raw-preview">
        <table className="w-full border-collapse font-mono text-xs">
          <caption className="sr-only">First {peek.rows.length} rows of the sheet, exactly as stored in the file</caption>
          <thead>
            <tr className="bg-muted text-muted-foreground">
              <th scope="col" className="sticky left-0 w-10 border-r bg-muted px-2 py-1.5 text-right font-medium">
                #
              </th>
              {Array.from({ length: width }, (_, c) => (
                <th scope="col" key={c} className="min-w-24 px-2 py-1.5 text-left font-medium">
                  {columnLetter(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {peek.rows.map((row, r) => {
              const isHeader = r === headerRow;
              const skipped = r < headerRow;
              return (
                <tr
                  key={r}
                  onClick={() => r < 20 && onHeaderRow(r)}
                  aria-label={isHeader ? `Row ${r + 1}, header row` : undefined}
                  className={cn(
                    "cursor-pointer border-t",
                    isHeader && "bg-primary/10 font-semibold text-foreground",
                    skipped && "text-muted-foreground line-through decoration-muted-foreground/50",
                  )}
                >
                  <th scope="row" className={cn("sticky left-0 border-r bg-card px-2 py-1.5 text-right font-normal text-muted-foreground", isHeader && "bg-accent")}>
                    {r + 1}
                  </th>
                  {Array.from({ length: width }, (_, c) => (
                    <td key={c} className="max-w-56 truncate px-2 py-1.5 whitespace-pre" title={row[c] ?? ""}>
                      {row[c] ?? ""}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        Showing the first {peek.rows.length} of {formatRows(peek.total_rows)}
        {peek.truncated_columns && `, first 50 of ${peek.total_columns} columns`}. Full preview with detected data types comes next.
      </p>
    </div>
  );
}

function formatRows(n: number) {
  return `${new Intl.NumberFormat("en-US").format(n)} row${n === 1 ? "" : "s"}`;
}
