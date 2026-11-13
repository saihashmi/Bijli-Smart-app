"use client";

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { api, ApiError, type Issue, type IssueRows } from "@/lib/api";
import { formatInteger } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const PAGE = 50;

/** Drill-down: the actual rows an issue affects, with their spreadsheet row numbers. */
export function IssueRowsDialog({ sessionId, issue, onClose }: { sessionId: string; issue: Issue | null; onClose: () => void }) {
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<IssueRows | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setOffset(0), [issue?.id]);
  useEffect(() => {
    if (!issue) return;
    let alive = true;
    setData(null);
    setError(null);
    api
      .issueRows(sessionId, issue.id, offset, PAGE)
      .then((d) => alive && setData(d))
      .catch((e: unknown) => alive && setError(e instanceof ApiError ? e.message : "Could not load the rows."));
    return () => {
      alive = false;
    };
  }, [sessionId, issue, offset]);

  return (
    <Dialog open={issue !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-4xl" data-testid="issue-rows">
        <DialogHeader>
          <DialogTitle>
            {issue?.title}
            {issue?.column && <span className="font-mono text-base font-normal text-muted-foreground"> · {issue.column}</span>}
          </DialogTitle>
          <DialogDescription>
            {data ? `${formatInteger(data.total)} affected row${data.total === 1 ? "" : "s"}, shown with their row numbers in your sheet.` : "Loading affected rows…"}
          </DialogDescription>
        </DialogHeader>
        {error && <p className="text-sm text-destructive-text">{error}</p>}
        {!data && !error && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Finding rows…
          </p>
        )}
        {data && (
          <>
            <div className="max-h-[55vh] overflow-auto rounded-lg border">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-muted text-muted-foreground">
                  <tr>
                    <th scope="col" className="px-2 py-1.5 text-left font-medium">
                      Row
                    </th>
                    {data.columns.map((c) => (
                      <th key={c} scope="col" className={cn("px-2 py-1.5 text-left font-medium whitespace-nowrap", c === data.highlight && "text-foreground")}>
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {data.rows.map((r) => (
                    <tr key={r.row} className="border-t">
                      <th scope="row" className="px-2 py-1.5 text-left font-sans font-normal text-muted-foreground tabular-nums">
                        {r.row}
                      </th>
                      {r.values.map((v, i) => (
                        <td key={i} className={cn("px-2 py-1.5 whitespace-pre", data.columns[i] === data.highlight && "bg-warning/10 font-semibold")}>
                          {v === null ? <span className="font-sans text-muted-foreground italic">empty</span> : v}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
      </DialogContent>
    </Dialog>
  );
}
