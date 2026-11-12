import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { contrastRatio, parseCssVars } from "@/lib/contrast";

const css = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8");
const light = parseCssVars(css, ":root");
const dark = { ...light, ...parseCssVars(css, ".dark") };

// [text token, background token, minimum ratio]. 4.5 = WCAG AA normal text, 3 = large text / UI parts.
const PAIRS: [string, string, number][] = [
  ["foreground", "background", 4.5],
  ["card-foreground", "card", 4.5],
  ["muted-foreground", "background", 4.5],
  ["muted-foreground", "muted", 4.5],
  ["muted-foreground", "card", 4.5],
  ["primary-foreground", "primary", 4.5],
  ["secondary-foreground", "secondary", 4.5],
  ["accent-foreground", "accent", 4.5],
  ["sidebar-foreground", "sidebar", 4.5],
  ["sidebar-accent-foreground", "sidebar-accent", 4.5],
  ["sidebar-primary-foreground", "sidebar-primary", 4.5],
  ["success-text", "background", 4.5],
  ["warning-text", "background", 4.5],
  ["destructive-text", "background", 4.5],
  ["teal-text", "background", 4.5],
  ["success-text", "card", 4.5],
  ["warning-text", "card", 4.5],
  ["destructive-text", "card", 4.5],
  ["link", "background", 4.5],
  ["link", "card", 4.5],
  ["ring", "background", 3],
];

describe("contrastRatio", () => {
  it("matches known WCAG values", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 1);
    expect(contrastRatio("#ffffff", "#ffffff")).toBeCloseTo(1, 5);
  });
});

for (const [name, theme] of [["light", light], ["dark", dark]] as const) {
  describe(`${name} theme tokens meet WCAG AA`, () => {
    it.each(PAIRS)("%s on %s ≥ %d:1", (fg, bg, min) => {
      expect(theme[fg], `missing --${fg}`).toBeDefined();
      expect(theme[bg], `missing --${bg}`).toBeDefined();
      expect(contrastRatio(theme[fg], theme[bg])).toBeGreaterThanOrEqual(min);
    });
  });
}
