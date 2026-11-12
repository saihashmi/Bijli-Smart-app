import type { DateDisplay } from "./api";

/** Format a date in the given IANA time zone using one of the supported display patterns. */
export function formatDate(date: Date, timeZone: string, display: DateDisplay): string {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" })
    .formatToParts(date)
    .reduce<Record<string, string>>((acc, p) => ({ ...acc, [p.type]: p.value }), {});
  const { day, month, year } = parts;
  if (display === "MM/DD/YYYY") return `${month}/${day}/${year}`;
  if (display === "YYYY-MM-DD") return `${year}-${month}-${day}`;
  return `${day}/${month}/${year}`;
}

/** Date + time with the time-zone abbreviation, e.g. "12/11/2026 22:31 PKT". */
export function formatDateTime(date: Date, timeZone: string, display: DateDisplay): string {
  const time = new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(date);
  const zone =
    new Intl.DateTimeFormat("en-US", { timeZone, timeZoneName: "short" }).formatToParts(date).find((p) => p.type === "timeZoneName")
      ?.value ?? timeZone;
  return `${formatDate(date, timeZone, display)} ${time} ${zone}`;
}

export function formatInteger(n: number): string {
  return new Intl.NumberFormat("en-US").format(n);
}

/** All IANA zones the browser knows, guaranteed to include the current value. */
export function timeZoneOptions(current?: string): string[] {
  const zones = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : ["Asia/Karachi", "UTC"];
  return current && !zones.includes(current) ? [current, ...zones] : zones;
}
