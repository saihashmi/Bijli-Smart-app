"use client";

import { useMemo, useState } from "react";
import { CheckCircle2, Lightbulb, Loader2, ShieldCheck } from "lucide-react";
import type { Issue, Severity } from "@/lib/api";
import { formatInteger } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";

const SEVERITY: Record<Severity, { label: string; variant: "destructive" | "warning" | "secondary" }> = {
  high: { label: "High", variant: "destructive" },
  medium: { label: "Medium", variant: "warning" },
  low: { label: "Low", variant: "secondary" },
};

export function IssueList({
  issues,
  onMarkSensitive,
  busyColumn,
}: {
  issues: Issue[];
  onMarkSensitive: (column: string) => void;
  busyColumn: string | null;
}) {
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [column, setColumn] = useState("");
  const columns = useMemo(() => [...new Set(issues.map((i) => i.column).filter(Boolean))] as string[], [issues]);
  const counts = useMemo(() => {
    const c = { all: issues.length, high: 0, medium: 0, low: 0 };
    issues.forEach((i) => (c[i.severity] += 1));
    return c;
  }, [issues]);
  const shown = issues.filter((i) => (severity === "all" || i.severity === severity) && (!column || i.column === column));

  if (issues.length === 0)
    return (
      <Card className="items-center py-10 text-center" data-testid="no-issues">
        <CheckCircle2 className="size-10 text-success" aria-hidden />
        <p className="font-semibold">No data-quality issues found</p>
        <p className="max-w-md px-6 text-sm text-muted-foreground">
          Structure looks clean. This does not guarantee the values are correct, so still sense-check totals you rely on.
        </p>
      </Card>
    );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div role="radiogroup" aria-label="Filter by severity" className="inline-flex w-fit flex-wrap rounded-lg border bg-muted p-0.5">
          {(["all", "high", "medium", "low"] as const).map((s) => (
            <button
              key={s}
              type="button"
              role="radio"
              aria-checked={severity === s}
              onClick={() => setSeverity(s)}
              className={cn(
                "cursor-pointer rounded-md px-3 py-1 text-sm font-medium text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring",
                severity === s && "bg-card text-foreground shadow-sm",
              )}
            >
              {s === "all" ? "All" : SEVERITY[s].label} <span className="tabular-nums">({counts[s]})</span>
            </button>
          ))}
        </div>
        <div className="w-full sm:w-64">
          <NativeSelect aria-label="Filter by column" value={column} onChange={(e) => setColumn(e.target.value)}>
            <option value="">All columns</option>
            {columns.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      <ul className="space-y-3" aria-label="Data-quality issues">
        {shown.map((issue) => (
          <li key={issue.id}>
            <Card className="gap-3 py-4" data-testid="issue">
              <CardContent className="space-y-3 px-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={SEVERITY[issue.severity].variant}>{SEVERITY[issue.severity].label}</Badge>
                  <h3 className="font-semibold">{issue.title}</h3>
                  {issue.column ? (
                    <Badge variant="outline" className="font-mono">
                      {issue.column}
                    </Badge>
                  ) : (
                    <Badge variant="outline">Whole sheet</Badge>
                  )}
                  <span className="ml-auto text-sm text-muted-foreground tabular-nums">
                    {formatInteger(issue.affected_rows)} {issue.details.unit === "cells" ? "cells" : issue.affected_rows === 1 ? "row" : "rows"}
                    {issue.details.unit !== "cells" && ` · ${issue.affected_pct}%`}
                  </span>
                </div>
                <p className="text-sm">{issue.description}</p>
                {issue.examples.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">Examples</p>
                    <ul className="flex flex-wrap gap-1.5">
                      {issue.examples.map((ex, i) => (
                        <li key={i} className="rounded-md border bg-muted/50 px-2 py-0.5 font-mono text-xs whitespace-pre">
                          {ex.row !== null && <span className="text-muted-foreground">Row {ex.row}: </span>}
                          {ex.value}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="flex flex-wrap items-center gap-2 border-t pt-3 text-sm">
                  <Lightbulb className="size-4 text-teal" aria-hidden />
                  <span>
                    <span className="text-muted-foreground">Suggested: </span>
                    {issue.suggested_action.label}
                  </span>
                  {issue.suggested_action.operation === "mark_sensitive" && issue.column ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="ml-auto"
                      disabled={busyColumn === issue.column}
                      onClick={() => onMarkSensitive(issue.column!)}
                    >
                      {busyColumn === issue.column ? <Loader2 className="animate-spin" /> : <ShieldCheck />} Mark as sensitive
                    </Button>
                  ) : issue.suggested_action.operation ? (
                    <span className="ml-auto text-xs text-muted-foreground">Apply it in the Cleaning Studio (Milestone 7)</span>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
      {shown.length === 0 && <p className="text-sm text-muted-foreground">No issues match these filters.</p>}
    </div>
  );
}
