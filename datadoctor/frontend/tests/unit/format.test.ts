import { describe, expect, it } from "vitest";
import { formatDate, formatDateTime, formatInteger, timeZoneOptions } from "@/lib/format";

// 12 Nov 2026 20:30 UTC = 13 Nov 2026 01:30 in Karachi (UTC+5): the date itself changes.
const instant = new Date(Date.UTC(2026, 10, 12, 20, 30));

describe("formatDate", () => {
  it("uses the selected time zone, not the computer's", () => {
    expect(formatDate(instant, "Asia/Karachi", "DD/MM/YYYY")).toBe("13/11/2026");
    expect(formatDate(instant, "UTC", "DD/MM/YYYY")).toBe("12/11/2026");
  });
  it("supports all three display patterns", () => {
    expect(formatDate(instant, "Asia/Karachi", "MM/DD/YYYY")).toBe("11/13/2026");
    expect(formatDate(instant, "Asia/Karachi", "YYYY-MM-DD")).toBe("2026-11-13");
  });
});

describe("formatDateTime", () => {
  it("includes 24-hour time and the zone", () => {
    expect(formatDateTime(instant, "Asia/Karachi", "DD/MM/YYYY")).toMatch(/^13\/11\/2026 01:30 (GMT\+5|PKT)$/);
  });
});

describe("helpers", () => {
  it("formats integers with thousands separators", () => {
    expect(formatInteger(20000000)).toBe("20,000,000");
  });
  it("time-zone list contains Karachi and keeps an unknown current value", () => {
    expect(timeZoneOptions()).toContain("Asia/Karachi");
    expect(timeZoneOptions("Etc/Custom")[0]).toBe("Etc/Custom");
  });
});

import { columnLetter, formatBytes, precheckFile } from "@/lib/format";

describe("upload helpers", () => {
  it("formats sizes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(20 * 1024 * 1024)).toBe("20.0 MB");
  });
  it("produces Excel column letters", () => {
    expect([0, 25, 26, 27, 701, 702].map(columnLetter)).toEqual(["A", "Z", "AA", "AB", "ZZ", "AAA"]);
  });
  it("pre-checks extension, emptiness and size", () => {
    expect(precheckFile({ name: "a.XLSX", size: 10 }, 20)).toBeNull();
    expect(precheckFile({ name: "a.pdf", size: 10 }, 20)).toMatch(/Unsupported/);
    expect(precheckFile({ name: "noext", size: 10 }, 20)).toMatch(/Unsupported/);
    expect(precheckFile({ name: "a.csv", size: 0 }, 20)).toMatch(/empty/);
    expect(precheckFile({ name: "a.csv", size: 21 * 1024 * 1024 }, 20)).toMatch(/20 MB/);
  });
});
