import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const FIX = path.join(__dirname, "fixtures");

/** WCAG 2.1 A/AA rules. Any violation fails the test and prints what and where. */
async function scan(page: Page, label: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const summary = results.violations.map(
    (v) =>
      `${v.id} (${v.impact}): ${v.help}\n    ${v.nodes
        .slice(0, 4)
        .map((n) => `${n.target.join(" ")} :: ${n.html.slice(0, 140)} :: ${(n.any[0]?.message ?? "").slice(0, 160)}`)
        .join("\n    ")}`,
  );
  expect(summary, `${label}: accessibility violations`).toEqual([]);
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    test(`public and workspace pages have no WCAG A/AA violations (${scheme})`, async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      for (const url of ["/", "/workspace", "/upload", "/settings"]) {
        await page.goto(url);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        await page.waitForLoadState("networkidle");
        await scan(page, url);
      }
    });

    test(`analysis screens have no WCAG A/AA violations (${scheme})`, async ({ page }) => {
      test.slow();
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.goto("/upload");
      await page.getByTestId("file-input").setInputFiles(path.join(FIX, "sales_small.xlsx"));
      await expect(page.getByTestId("raw-preview")).toBeVisible();
      await scan(page, "upload with a file");
      await page.getByRole("button", { name: "Start analysis" }).click();
      await expect(page).toHaveURL(/\/health$/);
      const base = page.url().replace(/\/health$/, "");
      await expect(page.getByTestId("health-score")).toBeVisible();
      await page.waitForLoadState("networkidle");
      await scan(page, "health");

      await page.goto(`${base}/clean?op=trim_whitespace`);
      await expect(page.getByTestId("data-grid")).toBeVisible();
      await page.waitForLoadState("networkidle");
      await scan(page, "clean");

      await page.goto(`${base}/dashboard`);
      await expect(page.getByTestId("widget").first()).toBeVisible();
      await expect(page.getByTestId("save-state")).toContainText("Saved");
      await scan(page, "dashboard");
      for (const theme of ["midnight", "minimal"]) {
        await page.getByLabel("Dashboard theme").selectOption(theme);
        await expect(page.getByTestId("dashboard-canvas")).toHaveAttribute("data-theme-id", theme);
        await page.waitForTimeout(300); // let colour transitions settle before measuring contrast
        await scan(page, `dashboard ${theme}`);
      }
      await page.getByRole("button", { name: "Add widget" }).click();
      await expect(page.getByTestId("editor-preview")).toBeVisible();
      await scan(page, "widget editor");
      await page.keyboard.press("Escape");

      await page.goto(`${base}/analyst`);
      await page.getByLabel("Your question").fill("Which region has the highest total amount?");
      await page.getByRole("button", { name: "Ask", exact: true }).click();
      await expect(page.getByTestId("answer")).toBeVisible();
      await scan(page, "analyst");

      await page.goto(`${base}/export`);
      await page.getByRole("button", { name: "Create Excel workbook" }).click();
      await expect(page.getByTestId("export-job")).toHaveCount(1);
      await scan(page, "export");
    });
  });
}
