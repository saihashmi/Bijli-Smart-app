"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AggRow, AggregateResult, ChartType, HistogramResult, QueryResult, ScatterResult, TableResult } from "@/lib/analytics";
import { formatCompact, formatFull, seriesColor, type ChartTheme } from "@/lib/chart-theme";

type DrillHandler = (row: AggRow) => void;

const clip = (s: string, n = 14) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

function TooltipBox({
  theme,
  title,
  lines,
}: {
  theme: ChartTheme;
  title: string;
  lines: { name: string; value: string; color?: string }[];
}) {
  return (
    <div
      className="max-w-64 rounded-lg px-3 py-2 text-xs shadow-lg"
      style={{ background: theme.tooltipBg, color: theme.tooltipText }}
    >
      <p className="mb-1 font-semibold break-words">{title}</p>
      {lines.map((l) => (
        <p key={l.name} className="flex items-center justify-between gap-4 tabular-nums">
          <span className="flex min-w-0 items-center gap-1.5">
            {l.color && <span className="size-2 shrink-0 rounded-full" style={{ background: l.color }} />}
            <span className="truncate opacity-80">{l.name}</span>
          </span>
          <span className="font-medium">{l.value}</span>
        </p>
      ))}
    </div>
  );
}

/* eslint-disable @typescript-eslint/no-explicit-any -- Recharts passes loosely typed payloads to custom renderers */
function aggTooltip(theme: ChartTheme, result: AggregateResult) {
  const AggTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const row = payload[0].payload as AggRow;
    const lines = result.series
      ? payload.map((p: any) => ({ name: String(p.name), value: formatFull(p.value), color: p.color }))
      : [{ name: result.measure.label, value: formatFull(row.value) }];
    lines.push({ name: "Rows in group", value: row.rows.toLocaleString("en-US") });
    return <TooltipBox theme={theme} title={row.label} lines={lines} />;
  };
  return AggTooltip;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

function axisProps(theme: ChartTheme) {
  return {
    stroke: theme.grid,
    tick: { fill: theme.axis, fontSize: 11 },
    tickLine: false,
  } as const;
}

function Cartesian({
  chart,
  result,
  theme,
  onDrill,
}: {
  chart: "bar" | "line" | "area";
  result: AggregateResult;
  theme: ChartTheme;
  onDrill?: DrillHandler;
}) {
  const names = result.series?.names ?? null;
  const data = result.rows.map((r) => ({ ...r, ...(r.values ?? {}) }));
  const stackable = result.measure.agg === "sum" || result.measure.agg === "count";
  const canDrill = Boolean(onDrill) && result.dimension?.kind !== "date";
  const common = {
    data,
    margin: { top: 8, right: 24, bottom: 4, left: 0 },
  };
  const axes = (
    <>
      <CartesianGrid stroke={theme.grid} strokeDasharray="3 3" vertical={false} />
      <XAxis dataKey="label" {...axisProps(theme)} tickFormatter={(v: string) => clip(String(v))} interval="preserveStartEnd" minTickGap={12} />
      <YAxis {...axisProps(theme)} axisLine={false} width={52} tickFormatter={(v: number) => formatCompact(v)} />
      <Tooltip content={aggTooltip(theme, result)} cursor={{ fill: theme.grid, opacity: 0.35 }} />
      {names && <Legend wrapperStyle={{ fontSize: 11, color: theme.muted }} iconType="circle" iconSize={8} />}
    </>
  );
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Recharts click payload
  const click = canDrill ? (d: any) => d?.payload && !d.payload.other && onDrill?.(d.payload as AggRow) : undefined;

  if (chart === "bar") {
    return (
      <BarChart {...common}>
        {axes}
        {names ? (
          names.map((n, i) => (
            <Bar key={n} dataKey={n} name={n} fill={seriesColor(theme, i)} stackId={stackable ? "s" : undefined} radius={stackable ? 0 : [3, 3, 0, 0]} maxBarSize={48} onClick={click} cursor={canDrill ? "pointer" : undefined} isAnimationActive={false} />
          ))
        ) : (
          <Bar dataKey="value" name={result.measure.label} fill={seriesColor(theme, 0)} radius={[4, 4, 0, 0]} maxBarSize={56} onClick={click} cursor={canDrill ? "pointer" : undefined} isAnimationActive={false}>
            {data.map((r) => (
              <Cell key={r.key} fill={r.other || r.missing ? theme.muted : seriesColor(theme, 0)} />
            ))}
          </Bar>
        )}
      </BarChart>
    );
  }
  const Chart = chart === "line" ? LineChart : AreaChart;
  const keys = names ?? ["value"];
  return (
    <Chart {...common}>
      {axes}
      {keys.map((k, i) =>
        chart === "line" ? (
          <Line key={k} type="monotone" dataKey={k} name={names ? k : result.measure.label} stroke={seriesColor(theme, i)} strokeWidth={2} dot={data.length <= 40 ? { r: 2.5 } : false} activeDot={{ r: 4 }} connectNulls={false} isAnimationActive={false} />
        ) : (
          <Area key={k} type="monotone" dataKey={k} name={names ? k : result.measure.label} stroke={seriesColor(theme, i)} fill={seriesColor(theme, i)} fillOpacity={0.18} strokeWidth={2} connectNulls={false} stackId={names && stackable ? "s" : undefined} isAnimationActive={false} />
        ),
      )}
    </Chart>
  );
}

function PieLike({ donut, result, theme, onDrill }: { donut: boolean; result: AggregateResult; theme: ChartTheme; onDrill?: DrillHandler }) {
  const data = result.rows.filter((r) => typeof r.value === "number" && r.value > 0);
  const canDrill = Boolean(onDrill) && result.dimension?.kind !== "date";
  return (
    <PieChart margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
      <Pie
        data={data}
        dataKey="value"
        nameKey="label"
        innerRadius={donut ? "55%" : 0}
        outerRadius="82%"
        paddingAngle={data.length > 1 ? 1.5 : 0}
        stroke={theme.card}
        strokeWidth={2}
        isAnimationActive={false}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Recharts click payload
        onClick={canDrill ? (d: any) => d?.payload && !d.payload.other && onDrill?.(d.payload as AggRow) : undefined}
        cursor={canDrill ? "pointer" : undefined}
      >
        {data.map((r, i) => (
          <Cell key={r.key} fill={r.other || r.missing ? theme.muted : seriesColor(theme, i)} />
        ))}
      </Pie>
      <Tooltip content={aggTooltip(theme, result)} />
      <Legend wrapperStyle={{ fontSize: 11, color: theme.muted }} iconType="circle" iconSize={8} formatter={(v: string) => clip(String(v), 22)} />
    </PieChart>
  );
}

function Histogram({ result, theme }: { result: HistogramResult; theme: ChartTheme }) {
  const data = result.bins.map((b) => ({ ...b, label: `${formatCompact(b.start)} – ${formatCompact(b.end)}` }));
  return (
    <BarChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 0 }} barCategoryGap={1}>
      <CartesianGrid stroke={theme.grid} strokeDasharray="3 3" vertical={false} />
      <XAxis dataKey="label" {...axisProps(theme)} interval="preserveStartEnd" minTickGap={24} />
      <YAxis {...axisProps(theme)} axisLine={false} width={44} allowDecimals={false} tickFormatter={(v: number) => formatCompact(v)} />
      <Tooltip
        cursor={{ fill: theme.grid, opacity: 0.35 }}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Recharts tooltip payload
        content={({ active, payload }: any) =>
          active && payload?.length ? (
            <TooltipBox
              theme={theme}
              title={`${formatFull(payload[0].payload.start)} to ${formatFull(payload[0].payload.end)}`}
              lines={[{ name: "Values", value: payload[0].payload.count.toLocaleString("en-US") }]}
            />
          ) : null
        }
      />
      <Bar dataKey="count" name="Values" fill={seriesColor(theme, 0)} radius={[2, 2, 0, 0]} isAnimationActive={false} />
    </BarChart>
  );
}

function ScatterPlot({ result, theme }: { result: ScatterResult; theme: ChartTheme }) {
  const data = result.points.map(([x, y]) => ({ x, y }));
  return (
    <ScatterChart margin={{ top: 8, right: 12, bottom: 18, left: 0 }}>
      <CartesianGrid stroke={theme.grid} strokeDasharray="3 3" />
      <XAxis type="number" dataKey="x" name={result.x} {...axisProps(theme)} tickFormatter={(v: number) => formatCompact(v)} domain={["auto", "auto"]} label={{ value: clip(result.x, 30), position: "insideBottom", offset: -10, fill: theme.muted, fontSize: 11 }} />
      <YAxis type="number" dataKey="y" name={result.y} {...axisProps(theme)} axisLine={false} width={52} tickFormatter={(v: number) => formatCompact(v)} domain={["auto", "auto"]} />
      <Tooltip
        cursor={{ stroke: theme.muted, strokeDasharray: "3 3" }}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Recharts tooltip payload
        content={({ active, payload }: any) =>
          active && payload?.length ? (
            <TooltipBox
              theme={theme}
              title="Point"
              lines={[
                { name: result.x, value: formatFull(payload[0].payload.x) },
                { name: result.y, value: formatFull(payload[0].payload.y) },
              ]}
            />
          ) : null
        }
      />
      <Scatter data={data} fill={seriesColor(theme, 0)} fillOpacity={0.55} isAnimationActive={false} />
    </ScatterChart>
  );
}

export function KpiValue({ result, theme }: { result: AggregateResult; theme: ChartTheme }) {
  const v = result.total.value;
  return (
    <div className="flex h-full flex-col justify-center gap-1" data-testid="kpi-value">
      <p className="text-3xl leading-tight font-semibold tracking-tight tabular-nums sm:text-4xl" style={{ color: theme.text }} title={formatFull(v)}>
        {v === null ? "No value" : formatCompact(v)}
      </p>
      <p className="text-xs" style={{ color: theme.muted }}>
        {result.measure.label}
        {typeof v === "number" && Math.abs(v) >= 10000 && <span className="tabular-nums"> · exactly {formatFull(v)}</span>}
      </p>
      {result.measure.column && (
        <p className="text-xs" style={{ color: theme.muted }}>
          From {result.total.n.toLocaleString("en-US")} usable values
        </p>
      )}
    </div>
  );
}

export function TableBody({ result, theme }: { result: TableResult; theme: ChartTheme }) {
  return (
    <div className="h-full overflow-auto" tabIndex={0} role="region" aria-label="Rows">
      <table className="w-full border-collapse text-left text-xs">
        <thead>
          <tr style={{ color: theme.muted }}>
            <th className="sticky top-0 px-2 py-1.5 font-medium" style={{ background: theme.card }}>
              Row
            </th>
            {result.columns.map((c) => (
              <th key={c} className="sticky top-0 px-2 py-1.5 font-medium whitespace-nowrap" style={{ background: theme.card }}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody style={{ color: theme.text }}>
          {result.rows.map((row, i) => (
            <tr key={result.row_numbers[i]} style={{ borderTop: `1px solid ${theme.grid}` }}>
              <td className="px-2 py-1.5 tabular-nums" style={{ color: theme.muted }}>
                {result.row_numbers[i]}
              </td>
              {row.map((cell, j) => (
                <td key={j} className="max-w-48 truncate px-2 py-1.5 font-mono" title={cell}>
                  {cell === "" ? "·" : cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The figures behind a chart as a plain table: the accessible alternative and the "view as table" mode. */
export function DataTable({ result, theme }: { result: QueryResult; theme: ChartTheme }) {
  let head: string[] = [];
  let rows: string[][] = [];
  if (result.kind === "aggregate") {
    const names = result.series?.names;
    head = [result.dimension?.column ?? "Measure", ...(names ?? [result.measure.label]), "Rows"];
    rows = result.dimension
      ? result.rows.map((r) => [
          r.label,
          ...(names ? names.map((n) => formatFull(r.values?.[n] ?? null)) : [formatFull(r.value)]),
          r.rows.toLocaleString("en-US"),
        ])
      : [[result.measure.label, formatFull(result.total.value), result.meta.rows_after_filters.toLocaleString("en-US")]];
  } else if (result.kind === "histogram") {
    head = ["From", "To", "Values"];
    rows = result.bins.map((b) => [formatFull(b.start), formatFull(b.end), b.count.toLocaleString("en-US")]);
  } else if (result.kind === "scatter") {
    head = [result.x, result.y];
    rows = result.points.slice(0, 200).map(([x, y]) => [formatFull(x), formatFull(y)]);
  } else {
    return <TableBody result={result} theme={theme} />;
  }
  return (
    <div className="h-full overflow-auto" tabIndex={0} role="region" aria-label="Chart data">
      <table className="w-full border-collapse text-left text-xs" data-testid="chart-table">
        <thead>
          <tr style={{ color: theme.muted }}>
            {head.map((h, i) => (
              <th key={i} className={`sticky top-0 px-2 py-1.5 font-medium ${i ? "text-right" : ""}`} style={{ background: theme.card }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody style={{ color: theme.text }}>
          {rows.map((r, i) => (
            <tr key={i} style={{ borderTop: `1px solid ${theme.grid}` }}>
              {r.map((c, j) => (
                <td key={j} className={`px-2 py-1.5 ${j ? "text-right tabular-nums" : "max-w-56 truncate"}`}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {result.kind === "scatter" && result.points.length > 200 && (
        <p className="px-2 py-1.5 text-xs" style={{ color: theme.muted }}>
          First 200 of {result.points.length.toLocaleString("en-US")} points.
        </p>
      )}
    </div>
  );
}

/** One sentence describing what the chart shows, for screen readers and as a caption. Uses only computed values. */
export function describe(result: QueryResult): string {
  if (result.kind === "aggregate") {
    if (!result.dimension) return `${result.measure.label}: ${formatFull(result.total.value)}.`;
    const valued = result.rows.filter((r) => typeof r.value === "number" && !r.other) as (AggRow & { value: number })[];
    if (!valued.length) return `${result.measure.label} by ${result.dimension.column}: no group has a value.`;
    const top = valued.reduce((a, b) => (b.value > a.value ? b : a));
    const low = valued.reduce((a, b) => (b.value < a.value ? b : a));
    const head = `${result.measure.label} by ${result.dimension.column}, ${result.rows.length} ${result.rows.length === 1 ? "group" : "groups"}.`;
    if (valued.length === 1) return `${head} ${top.label}: ${formatFull(top.value)}.`;
    if (top.value === low.value) return `${head} All groups have the same value (${formatFull(top.value)}).`;
    return `${head} Highest: ${top.label} (${formatFull(top.value)}). Lowest: ${low.label} (${formatFull(low.value)}).`;
  }
  if (result.kind === "histogram") {
    if (!result.stats) return `No numeric values in ${result.column}.`;
    return `Distribution of ${result.column}: ${result.meta.values_used?.toLocaleString("en-US")} values from ${formatFull(result.stats.min)} to ${formatFull(result.stats.max)}, median ${formatFull(result.stats.median)}.`;
  }
  if (result.kind === "scatter") {
    const r = result.pearson_r;
    return `${result.y} against ${result.x}: ${result.meta.pairs_used?.toLocaleString("en-US")} points${r === null ? "" : `, correlation (Pearson r) ${r.toFixed(2)}`}.`;
  }
  return `Table of ${result.total.toLocaleString("en-US")} rows.`;
}

/** Why a chart cannot be drawn from this result, or null when it can. */
export function emptyReason(chart: ChartType, result: QueryResult): string | null {
  if (result.meta.rows_after_filters === 0) return result.meta.rows_total ? "No rows match the current filters." : "The data has no rows.";
  if (result.kind === "aggregate") {
    if (chart === "kpi") return null;
    if (!result.dimension) return "Choose a column to group by.";
    if (!result.rows.length) return `No row has a usable value in “${result.dimension.column}”.`;
    if (result.rows.every((r) => r.value === null)) return `No group has a usable value for ${result.measure.label.toLowerCase()}.`;
    if ((chart === "pie" || chart === "donut") && result.rows.some((r) => typeof r.value === "number" && r.value < 0))
      return "A pie or donut chart cannot show negative values. Use a bar chart instead.";
    if ((chart === "pie" || chart === "donut") && !result.rows.some((r) => typeof r.value === "number" && r.value > 0))
      return "There are no positive values to show as shares.";
    if (result.rows.some((r) => typeof r.value === "string")) return "Dates cannot be drawn on this chart. Use a KPI card or a table.";
    return null;
  }
  if (result.kind === "histogram") return result.bins.length ? null : `“${result.column}” has no numeric values in the selected rows.`;
  if (result.kind === "scatter") return result.points.length ? null : "No row has a number in both columns.";
  return result.rows.length ? null : "No rows to show.";
}

export function ChartBody({
  chart,
  result,
  theme,
  onDrill,
}: {
  chart: ChartType;
  result: QueryResult;
  theme: ChartTheme;
  onDrill?: DrillHandler;
}) {
  if (chart === "kpi" && result.kind === "aggregate") return <KpiValue result={result} theme={theme} />;
  if (chart === "table" && result.kind === "table") return <TableBody result={result} theme={theme} />;
  let inner: React.ReactElement | null = null;
  if (result.kind === "aggregate" && (chart === "bar" || chart === "line" || chart === "area"))
    inner = <Cartesian chart={chart} result={result} theme={theme} onDrill={onDrill} />;
  else if (result.kind === "aggregate" && (chart === "pie" || chart === "donut"))
    inner = <PieLike donut={chart === "donut"} result={result} theme={theme} onDrill={onDrill} />;
  else if (result.kind === "histogram") inner = <Histogram result={result} theme={theme} />;
  else if (result.kind === "scatter") inner = <ScatterPlot result={result} theme={theme} />;
  if (!inner) return null;
  return (
    <ResponsiveContainer width="100%" height="100%" minWidth={0}>
      {inner}
    </ResponsiveContainer>
  );
}
