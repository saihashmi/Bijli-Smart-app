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
