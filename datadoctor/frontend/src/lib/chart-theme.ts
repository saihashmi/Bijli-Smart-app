/** Chart theme system: three dashboard themes with literal colours (so exported images match the screen). */
import type { DashboardTheme } from "./analytics";

export type ChartTheme = {
  id: DashboardTheme;
  name: string;
  description: string;
  dark: boolean;
  canvas: string;
  card: string;
  cardBorder: string;
  text: string;
  muted: string;
  grid: string;
  axis: string;
  accent: string;
  series: string[];
  tooltipBg: string;
  tooltipText: string;
  cardClass: string;
};

export const CHART_THEMES: Record<DashboardTheme, ChartTheme> = {
  midnight: {
    id: "midnight",
    name: "Midnight Intelligence",
    description: "Dark canvas with luminous series colours",
    dark: true,
    canvas: "#080D1B",
    card: "#111827",
    cardBorder: "#243049",
    text: "#F8FAFC",
    muted: "#94A3B8",
    grid: "#243049",
    axis: "#94A3B8",
    accent: "#22D3EE",
    series: ["#3B82F6", "#22D3EE", "#8B5CF6", "#14B8A6", "#F59E0B", "#F43F5E", "#84CC16", "#94A3B8"],
    tooltipBg: "#172033",
    tooltipText: "#F8FAFC",
    cardClass: "shadow-[0_0_0_1px_rgba(59,130,246,0.08),0_12px_32px_-12px_rgba(0,0,0,0.6)]",
  },
  executive: {
    id: "executive",
    name: "Executive Light",
    description: "Bright, print-friendly and formal",
    dark: false,
    canvas: "#F8FAFC",
    card: "#FFFFFF",
    cardBorder: "#E2E8F0",
    text: "#0F172A",
    muted: "#475569",
    grid: "#E2E8F0",
    axis: "#475569",
    accent: "#2563EB",
    series: ["#2563EB", "#0F766E", "#7C3AED", "#0891B2", "#B45309", "#BE123C", "#4D7C0F", "#64748B"],
    tooltipBg: "#0F172A",
    tooltipText: "#F8FAFC",
    cardClass: "shadow-sm",
  },
  minimal: {
    id: "minimal",
    name: "Minimal Analytics",
    description: "Quiet greys with one accent colour",
    dark: false,
    canvas: "#FFFFFF",
    card: "#FFFFFF",
    cardBorder: "#D4D4D8",
    text: "#18181B",
    muted: "#52525B",
    grid: "#E4E4E7",
    axis: "#52525B",
    accent: "#2563EB",
    series: ["#2563EB", "#18181B", "#71717A", "#1D4ED8", "#A1A1AA", "#3F3F46", "#60A5FA", "#52525B"],
    tooltipBg: "#18181B",
    tooltipText: "#FAFAFA",
    cardClass: "",
  },
};

/** Stable colour per series name: the same label keeps its colour on every chart of a dashboard. */
export function seriesColor(theme: ChartTheme, index: number): string {
  return theme.series[index % theme.series.length];
}

const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const full = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

/** Short axis/KPI form (12.5K). Never used as the only representation: the full value is always available. */
export function formatCompact(v: number | string | null | undefined): string {
  if (v === null || v === undefined) return "–";
  if (typeof v === "string") return v;
  return Math.abs(v) >= 10000 ? compact.format(v) : full.format(v);
}

export function formatFull(v: number | string | null | undefined): string {
  if (v === null || v === undefined) return "No value";
  if (typeof v === "string") return v;
  return full.format(v);
}
