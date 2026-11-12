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

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Spreadsheet-style column letters: 0 → A, 25 → Z, 26 → AA. */
export function columnLetter(index: number): string {
  let n = index + 1;
  let out = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    out = String.fromCharCode(65 + r) + out;
    n = Math.floor((n - 1) / 26);
  }
  return out;
}

export const ACCEPTED_EXTENSIONS = [".xlsx", ".xlsm", ".xls", ".csv", ".txt"];

/** Client-side pre-check (the server re-validates everything). Returns an error message or null. */
export function precheckFile(file: { name: string; size: number }, maxMb: number): string | null {
  const ext = file.name.includes(".") ? file.name.slice(file.name.lastIndexOf(".")).toLowerCase() : "";
  if (!ACCEPTED_EXTENSIONS.includes(ext)) return "Unsupported file type. Upload an Excel (.xlsx, .xls) or CSV file.";
  if (file.size === 0) return "The file is empty.";
  if (file.size > maxMb * 1024 * 1024) return `The file is larger than the ${maxMb} MB limit.`;
  return null;
}
