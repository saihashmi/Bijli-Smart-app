"use client";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ReferenceArea, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { AlertTriangle, CalendarRange, Coins, Gauge, PiggyBank, TrendingDown, TrendingUp, Minus, Zap } from "lucide-react";
import type { Analysis } from "@/lib/api";
import { fmt } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const axis = { stroke: "var(--muted-foreground)", fontSize: 11, tickLine: false, axisLine: false } as const;

function ChartTooltip({ active, payload, label, unit = "kWh", currency }: {
  active?: boolean; payload?: { name: string; value: number; payload: Record<string, unknown> }[];
  label?: string | number; unit?: string; currency?: string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-md border bg-card px-3 py-2 text-xs shadow-md">
      <div className="mb-1 font-medium">{String(label)}</div>
      <div>{fmt(payload[0].value, 3)} {unit}</div>
      {typeof row.cost === "number" && <div className="text-muted-foreground">{currency} {fmt(row.cost)}</div>}
      {typeof row.change_pct === "number" && (
        <div className="text-muted-foreground">{row.change_pct > 0 ? "+" : ""}{fmt(row.change_pct, 1)}% vs previous</div>
      )}
    </div>
  );
}

function Kpi({ icon: Icon, label, value, sub }: { icon: typeof Zap; label: string; value: string; sub?: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Icon className="h-3.5 w-3.5" /> {label}
        </div>
        <div className="mt-1.5 text-2xl font-semibold tracking-tight">{value}</div>
        {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
      </CardContent>
    </Card>
  );
}

export function Dashboard({ a }: { a: Analysis }) {
  const s = a.summary;
  const cur = s.currency;
  const anomalyDates = new Set(a.anomalies.map((x) => x.date));
  const isMonthly = s.granularity === "monthly" || s.granularity === "weekly";
  const TrendIcon = a.trend?.direction === "rising" ? TrendingUp : a.trend?.direction === "falling" ? TrendingDown : Minus;
  const peakStart = a.settings.peak_start_hour;
  const peakEnd = a.settings.peak_end_hour;

  return (
    <div className="space-y-6">
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Kpi icon={Zap} label="Total consumption" value={`${fmt(s.total_kwh)} kWh`} sub={`${fmt(s.records)} records · ${s.granularity}`} />
        <Kpi icon={Gauge} label="Average per day" value={s.avg_daily_kwh !== null ? `${fmt(s.avg_daily_kwh)} kWh` : "–"}
          sub={s.peak_day ? `Peak ${s.peak_day.date}: ${fmt(s.peak_day.kwh)} kWh` : s.peak_month ? `Peak month ${s.peak_month.month}` : undefined} />
        <Kpi icon={Coins} label="Total cost" value={s.total_cost !== null ? `${cur} ${fmt(s.total_cost)}` : "–"}
          sub={s.cost_source === "file" ? "From billed amounts" : s.cost_source === "tariff" ? "From your tariff" : "Add a tariff in Settings"} />
        <Kpi icon={CalendarRange} label="Period" value={`${s.span_days} days`}
          sub={`${s.start.slice(0, 10)} → ${s.end.slice(0, 10)}`} />
      </div>

      <Card>
        <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
          <div className="space-y-1.5">
            <CardTitle>{isMonthly ? "Monthly consumption" : "Daily consumption"}</CardTitle>
            <CardDescription>
              {isMonthly ? "Total kWh per month" : "Total kWh per day. Red dots mark unusual days."}
            </CardDescription>
          </div>
          {a.trend && (
            <Badge variant={a.trend.direction === "rising" ? "warning" : a.trend.direction === "falling" ? "success" : "secondary"}>
              <TrendIcon className="h-3 w-3" /> {a.trend.direction}
              {a.trend.change_pct !== null && ` ${a.trend.change_pct > 0 ? "+" : ""}${fmt(a.trend.change_pct, 1)}%`}
            </Badge>
          )}
        </CardHeader>
        <CardContent className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            {isMonthly ? (
              <BarChart data={a.monthly} margin={{ left: -10, right: 8 }}>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis dataKey="month" {...axis} />
                <YAxis {...axis} />
                <Tooltip cursor={{ fill: "var(--muted)" }} content={<ChartTooltip currency={cur} />} />
                <Bar dataKey="kwh" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
              </BarChart>
            ) : (
              <AreaChart data={a.daily} margin={{ left: -10, right: 8 }}>
                <defs>
                  <linearGradient id="fillKwh" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--chart-1)" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="var(--chart-1)" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis dataKey="date" {...axis} tickFormatter={(d: string) => d.slice(5)} minTickGap={24} />
                <YAxis {...axis} />
                <Tooltip content={<ChartTooltip currency={cur} />} />
                <Area type="monotone" dataKey="kwh" stroke="var(--chart-1)" strokeWidth={2} fill="url(#fillKwh)" />
                {a.daily.filter((d) => anomalyDates.has(d.date)).map((d) => (
                  <ReferenceDot key={d.date} x={d.date} y={d.kwh} r={5} fill="var(--destructive)" stroke="var(--card)" strokeWidth={2} />
                ))}
              </AreaChart>
            )}
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {!isMonthly && a.monthly.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>By month</CardTitle>
              <CardDescription>Total kWh{s.cost_source ? ` and ${cur} cost` : ""} per calendar month</CardDescription>
            </CardHeader>
            <CardContent className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={a.monthly} margin={{ left: -10, right: 8 }}>
                  <CartesianGrid vertical={false} stroke="var(--border)" />
                  <XAxis dataKey="month" {...axis} />
                  <YAxis {...axis} />
                  <Tooltip cursor={{ fill: "var(--muted)" }} content={<ChartTooltip currency={cur} />} />
                  <Bar dataKey="kwh" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {a.hourly && (
          <Card>
            <CardHeader>
              <CardTitle>Time of day</CardTitle>
              <CardDescription>
                Average kWh per hour. Shaded: peak window {a.peak_hours?.window}
                {a.peak_hours && ` — ${fmt(a.peak_hours.share_pct, 1)}% of use in ${fmt(a.peak_hours.even_share_pct, 1)}% of the day`}
              </CardDescription>
            </CardHeader>
            <CardContent className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={a.hourly} margin={{ left: -10, right: 8 }}>
                  <CartesianGrid vertical={false} stroke="var(--border)" />
                  {peakEnd > peakStart && (
                    <ReferenceArea x1={peakStart} x2={peakEnd - 1} fill="var(--chart-2)" fillOpacity={0.15} />
                  )}
                  <XAxis dataKey="hour" {...axis} tickFormatter={(h: number) => `${h}h`} interval={2} />
                  <YAxis {...axis} />
                  <Tooltip cursor={{ fill: "var(--muted)" }} content={<ChartTooltip />} labelFormatter={(h) => `${h}:00`} />
                  <Bar dataKey="avg_kwh" radius={[3, 3, 0, 0]}>
                    {a.hourly.map((h) => (
                      <Cell key={h.hour}
                        fill={(peakEnd > peakStart ? h.hour >= peakStart && h.hour < peakEnd : h.hour >= peakStart || h.hour < peakEnd)
                          ? "var(--chart-2)" : "var(--chart-1)"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {a.weekday && (
          <Card>
            <CardHeader>
              <CardTitle>Day of week</CardTitle>
              <CardDescription>Average kWh per day</CardDescription>
            </CardHeader>
            <CardContent className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={a.weekday} margin={{ left: -10, right: 8 }}>
                  <CartesianGrid vertical={false} stroke="var(--border)" />
                  <XAxis dataKey="day" {...axis} />
                  <YAxis {...axis} />
                  <Tooltip cursor={{ fill: "var(--muted)" }} content={<ChartTooltip />} />
                  <Bar dataKey="avg_kwh" fill="var(--chart-3)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {a.categories && a.categories.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>By category</CardTitle>
              <CardDescription>Share of total kWh</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {a.categories.slice(0, 10).map((c, i) => (
                <div key={c.category}>
                  <div className="mb-1 flex justify-between gap-3 text-sm">
                    <span className="truncate font-medium">{c.category}</span>
                    <span className="shrink-0 text-muted-foreground">
                      {fmt(c.kwh)} kWh · {fmt(c.share_pct, 1)}%{c.cost !== undefined && ` · ${cur} ${fmt(c.cost)}`}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-muted">
                    <div className="h-2 rounded-full" style={{ width: `${c.share_pct}%`, background: `var(--chart-${(i % 5) + 1})` }} />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {a.baseload && (
          <Card>
            <CardHeader>
              <CardTitle>Always-on load</CardTitle>
              <CardDescription>Typical lowest hourly draw: fridges, routers, standby, leaks</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-semibold">{fmt(a.baseload.kw, 3)} kW</div>
              <p className="mt-1 text-sm text-muted-foreground">
                {fmt(a.baseload.kwh)} kWh over {fmt(a.baseload.hours_observed)} hours — {fmt(a.baseload.share_pct, 1)}% of all use.
              </p>
              <div className="mt-4 h-2 rounded-full bg-muted">
                <div className="h-2 rounded-full bg-chart-4" style={{ width: `${Math.min(100, a.baseload.share_pct)}%` }} />
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><PiggyBank className="h-4 w-4 text-primary" /> Savings scenarios</CardTitle>
            <CardDescription>Arithmetic on your own figures{s.effective_rate ? ` at ${cur} ${fmt(s.effective_rate, 3)}/kWh` : ""}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {a.savings.map((sv) => (
              <div key={sv.id} className="rounded-lg border p-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-medium">{sv.title}</span>
                  <span className="text-sm font-semibold text-success">
                    {fmt(sv.kwh)} kWh{sv.cost !== null && ` · ${cur} ${fmt(sv.cost)}`}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{sv.basis}</p>
              </div>
            ))}
            {!s.effective_rate && (
              <p className="text-xs text-muted-foreground">Add your tariff in Settings to see savings in money.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-warning" /> Unusual days</CardTitle>
            <CardDescription>Days far from a typical day (robust z-score on daily totals)</CardDescription>
          </CardHeader>
          <CardContent>
            {a.anomalies.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {isMonthly ? "Day-level anomaly detection needs daily or hourly data." : "No unusual days found."}
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow><TableHead>Date</TableHead><TableHead className="text-right">kWh</TableHead>
                    <TableHead className="text-right">Typical</TableHead><TableHead className="text-right">Deviation</TableHead></TableRow>
                </TableHeader>
                <TableBody>
                  {a.anomalies.slice(0, 10).map((x) => (
                    <TableRow key={x.date}>
                      <TableCell>{x.date}</TableCell>
                      <TableCell className="text-right font-medium">{fmt(x.kwh)}</TableCell>
                      <TableCell className="text-right text-muted-foreground">{fmt(x.typical_kwh)}</TableCell>
                      <TableCell className="text-right">
                        <Badge variant={x.direction === "high" ? "destructive" : "secondary"}>
                          {x.deviation_pct > 0 ? "+" : ""}{fmt(x.deviation_pct, 1)}%
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
