"use client";

import { useRef, useState } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, BarChart3, ImageDown, Info, Pencil, Table2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { exclusionNotes, type AggRow, type QueryOutcome, type Widget } from "@/lib/analytics";
import type { ChartTheme } from "@/lib/chart-theme";
import { exportChartPng, safeFileName } from "@/lib/export-png";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ChartBody, DataTable, describe, emptyReason } from "./charts";

const SPAN: Record<number, string> = {
  3: "col-span-12 sm:col-span-6 xl:col-span-3",
  4: "col-span-12 sm:col-span-6 xl:col-span-4",
  6: "col-span-12 lg:col-span-6",
  8: "col-span-12 lg:col-span-8",
  12: "col-span-12",
};

function IconButton({
  label,
  theme,
  onClick,
  pressed,
  disabled,
  children,
}: {
  label: string;
  theme: ChartTheme;
  onClick: () => void;
  pressed?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          aria-pressed={pressed}
          disabled={disabled}
          onClick={onClick}
          className="grid size-7 cursor-pointer place-items-center rounded-md outline-none transition-colors hover:bg-black/10 focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-35 dark:hover:bg-white/10"
          style={{ color: pressed ? theme.accent : theme.muted, background: pressed ? `${theme.accent}1f` : undefined }}
        >
          {children}
        </button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

export function WidgetCard({
  widget,
  outcome,
  loading,
  theme,
  customizing,
  isFirst,
  isLast,
  onEdit,
  onRemove,
  onMove,
  onDrill,
}: {
  widget: Widget;
  outcome: QueryOutcome | undefined;
  loading: boolean;
  theme: ChartTheme;
  customizing: boolean;
  isFirst: boolean;
  isLast: boolean;
  onEdit: () => void;
  onRemove: () => void;
  onMove: (delta: -1 | 1) => void;
  onDrill: (column: string, row: AggRow) => void;
}) {
  const [asTable, setAsTable] = useState(false);
  const body = useRef<HTMLDivElement>(null);
  const result = outcome?.ok ? outcome.result : null;
  const isKpi = widget.chart === "kpi";
  const isChart = !isKpi && widget.chart !== "table";
  const reason = result ? emptyReason(widget.chart, result) : null;
  const notes = result ? exclusionNotes(result) : [];
  const drillColumn = result?.kind === "aggregate" && result.dimension && result.dimension.kind !== "date" ? result.dimension.column : null;

  const savePng = async () => {
    if (!body.current) return;
    try {
      await exportChartPng(body.current, { title: widget.title, background: theme.card, text: theme.text, fileName: safeFileName(widget.title) });
      toast.success("Chart image saved.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "The image could not be saved.");
    }
  };

  return (
    <section
      aria-label={widget.title}
      data-testid="widget"
      data-widget-id={widget.id}
      data-chart={widget.chart}
      className={cn("flex min-w-0 flex-col rounded-2xl border p-4", SPAN[widget.width], theme.cardClass)}
      style={{ background: theme.card, borderColor: theme.cardBorder, color: theme.text }}
    >
      <header className="mb-2 flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          <h3 className={cn("min-w-0 font-semibold break-words", isKpi ? "text-xs tracking-wide uppercase" : "text-sm")} style={isKpi ? { color: theme.muted } : undefined}>
            {widget.title}
          </h3>
          {widget.reason && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" aria-label="Why this was suggested" className="shrink-0 cursor-help rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring" style={{ color: theme.muted }}>
                  <Info className="size-3.5" aria-hidden />
                </button>
              </TooltipTrigger>
              <TooltipContent>Suggested because: {widget.reason}</TooltipContent>
            </Tooltip>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          {customizing ? (
            <>
              <IconButton label="Move earlier" theme={theme} onClick={() => onMove(-1)} disabled={isFirst}>
                <ArrowLeft className="size-4" aria-hidden />
              </IconButton>
              <IconButton label="Move later" theme={theme} onClick={() => onMove(1)} disabled={isLast}>
                <ArrowRight className="size-4" aria-hidden />
              </IconButton>
              <IconButton label={`Edit ${widget.title}`} theme={theme} onClick={onEdit}>
                <Pencil className="size-4" aria-hidden />
              </IconButton>
              <IconButton label={`Remove ${widget.title}`} theme={theme} onClick={onRemove}>
                <Trash2 className="size-4" aria-hidden />
              </IconButton>
            </>
          ) : (
            isChart &&
            result &&
            !reason && (
              <>
                <IconButton label={asTable ? "Show as chart" : "Show as table"} theme={theme} onClick={() => setAsTable((v) => !v)} pressed={asTable}>
                  {asTable ? <BarChart3 className="size-4" aria-hidden /> : <Table2 className="size-4" aria-hidden />}
                </IconButton>
                <IconButton label="Save chart as image" theme={theme} onClick={savePng} disabled={asTable}>
                  <ImageDown className="size-4" aria-hidden />
                </IconButton>
              </>
            )
          )}
        </div>
      </header>

      <div ref={body} className={cn("relative w-full min-w-0 overflow-hidden", isKpi ? "min-h-20 flex-1" : "h-64 shrink-0")} aria-busy={loading}>
        {!outcome && loading && (
          <div className="absolute inset-0 animate-pulse rounded-xl" style={{ background: theme.grid, opacity: 0.5 }} role="status" aria-label="Calculating" />
        )}
        {outcome && !outcome.ok && (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center" role="alert">
            <AlertTriangle className="size-6" style={{ color: "#F59E0B" }} aria-hidden />
            <p className="max-w-xs text-sm">{outcome.error.message}</p>
            <p className="text-xs" style={{ color: theme.muted }}>
              Edit this widget or remove it.
            </p>
          </div>
        )}
        {result && reason && (
          <div className="flex h-full items-center justify-center text-center" data-testid="widget-empty">
            <p className="max-w-xs text-sm" style={{ color: theme.muted }}>
              {reason}
            </p>
          </div>
        )}
        {result && !reason && (
          <>
            {asTable ? (
              <DataTable result={result} theme={theme} />
            ) : (
              <div className="h-full w-full min-w-0" role={isChart ? "img" : undefined} aria-label={isChart ? describe(result) : undefined}>
                <ChartBody chart={widget.chart} result={result} theme={theme} onDrill={drillColumn ? (row) => onDrill(drillColumn, row) : undefined} />
              </div>
            )}
          </>
        )}
      </div>

      {result && !reason && isChart && (
        <p className="mt-2 text-xs" style={{ color: theme.muted }} data-testid="widget-summary">
          {describe(result)}
          {drillColumn && !asTable && " Select a bar or slice to filter the dashboard."}
        </p>
      )}
      {notes.length > 0 && (
        <ul className="mt-2 space-y-0.5 border-t pt-2 text-xs" style={{ color: theme.muted, borderColor: theme.grid }} data-testid="widget-notes">
          {notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
