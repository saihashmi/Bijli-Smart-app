"use client";

import { useEffect, useState } from "react";
import { animate, useReducedMotion } from "motion/react";
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

const R = 84;
const CIRC = 2 * Math.PI * R;
const SWEEP = 0.75; // 270° gauge

/** Circular gauge with one reveal animation (instant when reduced motion is requested). */
function Gauge({ score, stroke, band, bandClass }: { score: number; stroke: string; band: string; bandClass: string }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? score : 0);
  useEffect(() => {
    if (reduce) {
      setShown(score);
      return;
    }
    const controls = animate(0, score, { duration: 0.9, ease: [0.22, 1, 0.36, 1], onUpdate: (v) => setShown(Math.round(v)) });
    return () => controls.stop();
  }, [score, reduce]);

  return (
    <div className="relative mx-auto aspect-square w-full max-w-60" role="img" aria-label={`Data Health Score ${score} out of 100: ${band}`}>
      <svg viewBox="0 0 200 200" className="size-full -rotate-[225deg]" aria-hidden>
        <circle cx="100" cy="100" r={R} fill="none" stroke="var(--muted)" strokeWidth="14" strokeLinecap="round" strokeDasharray={`${CIRC * SWEEP} ${CIRC}`} />
        <circle
          cx="100"
          cy="100"
          r={R}
          fill="none"
          stroke={stroke}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={`${CIRC * SWEEP * (shown / 100)} ${CIRC}`}
          style={{ filter: `drop-shadow(0 0 8px ${stroke})` }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <p className="text-6xl leading-none font-bold tracking-tight tabular-nums" data-testid="health-score" aria-hidden>
            {shown}
          </p>
          <p className="mt-1 text-xs text-muted-foreground" aria-hidden>
            out of 100
          </p>
          <p className={cn("mt-1.5 text-sm font-semibold", bandClass)} aria-hidden>
            {band}
          </p>
        </div>
      </div>
    </div>
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
    <Card data-testid="score-card" className="h-full">
      <CardHeader>
        <CardTitle>Data Health Score</CardTitle>
        <CardDescription>Structural quality of this sheet, from 0 to 100.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <Gauge score={health.score} stroke={style.stroke} band={health.band} bandClass={style.text} />

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
                <div className="h-1.5 rounded-full bg-brand-gradient" style={{ width: `${c.value * 100}%` }} />
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">{c.explanation}</p>
            </li>
          ))}
        </ul>

        <details className="group rounded-lg border bg-muted/40 px-3 py-2 text-sm">
          <summary className="flex cursor-pointer items-center gap-2 font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <Calculator className="size-4 text-teal-text" aria-hidden /> How is this calculated?
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
