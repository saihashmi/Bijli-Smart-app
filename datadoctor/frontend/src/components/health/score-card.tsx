"use client";

import { Calculator } from "lucide-react";
import type { Health } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const LABELS: Record<string, string> = {
  completeness: "Completeness",
  uniqueness: "Uniqueness",
  type_consistency: "Type consistency",
  format_consistency: "Format consistency",
};

const BAND_STYLE: Record<Health["band"], { stroke: string; text: string }> = {
  Excellent: { stroke: "var(--success)", text: "text-success-text" },
  Good: { stroke: "var(--teal)", text: "text-teal-text" },
  "Needs attention": { stroke: "var(--warning)", text: "text-warning-text" },
  Poor: { stroke: "var(--destructive)", text: "text-destructive-text" },
};

function Gauge({ score, stroke }: { score: number; stroke: string }) {
  // Semicircle: radius 80, length π·80.
  const length = Math.PI * 80;
  return (
    <svg viewBox="0 0 200 112" className="w-full max-w-56" aria-hidden>
      <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="var(--muted)" strokeWidth="16" strokeLinecap="round" />
      <path
        d="M 20 100 A 80 80 0 0 1 180 100"
        fill="none"
        stroke={stroke}
        strokeWidth="16"
        strokeLinecap="round"
        strokeDasharray={`${(score / 100) * length} ${length}`}
      />
    </svg>
  );
}

export function ScoreCard({ health }: { health: Health | null }) {
  if (!health)
    return (
      <Card>
        <CardHeader>
          <CardTitle>Data Health Score</CardTitle>
          <CardDescription>Not enough data to score: the sheet has no data rows.</CardDescription>
        </CardHeader>
      </Card>
    );
  const style = BAND_STYLE[health.band];
  return (
    <Card data-testid="score-card">
      <CardHeader>
        <CardTitle>Data Health Score</CardTitle>
        <CardDescription>Structural quality of this sheet, from 0 to 100.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="relative mx-auto flex max-w-56 flex-col items-center">
          <Gauge score={health.score} stroke={style.stroke} />
          <div className="absolute inset-x-0 bottom-0 text-center">
            <p className="text-4xl font-bold tabular-nums" data-testid="health-score">
              {health.score}
            </p>
            <p className={cn("text-sm font-semibold", style.text)}>{health.band}</p>
          </div>
        </div>

        <ul className="space-y-3" aria-label="Score breakdown">
          {health.components.map((c) => (
            <li key={c.key} className="text-sm">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium">{LABELS[c.key] ?? c.key}</span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {(c.value * 100).toFixed(1)}% × {c.weight} = <span className="font-semibold text-foreground">{c.points.toFixed(1)}</span> pts
                </span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-muted" aria-hidden>
                <div className="h-1.5 rounded-full bg-primary" style={{ width: `${c.value * 100}%` }} />
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">{c.explanation}</p>
            </li>
          ))}
        </ul>

        <details className="group rounded-lg border bg-muted/40 px-3 py-2 text-sm">
          <summary className="flex cursor-pointer items-center gap-2 font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <Calculator className="size-4 text-teal" aria-hidden /> How is this calculated?
          </summary>
          <div className="mt-2 space-y-2 text-xs text-muted-foreground">
            <p className="font-mono text-[11px] text-foreground">{health.formula}</p>
            <p>Bands: 90–100 Excellent · 75–89 Good · 50–74 Needs attention · 0–49 Poor.</p>
            <p className="font-medium text-foreground">What the score does not tell you</p>
            <ul className="list-disc space-y-1 pl-4">
              {health.limitations.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </div>
        </details>
      </CardContent>
    </Card>
  );
}
