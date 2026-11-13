import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const FIX = path.join(__dirname, "fixtures");
const SHOTS = process.env.SCREENSHOT_DIR;

// sales_small.xlsx: 60 orders, 3 regions, 2 channels. Two orders have no Amount.
// Amount totals by hand: North 5,710, South 6,780, East 6,770 = 19,260 over 58 values (average 332.07).

async function openDashboard(page: Page) {
  await page.goto("/upload");
  await page.getByTestId("file-input").setInputFiles(path.join(FIX, "sales_small.xlsx"));
  await expect(page.getByTestId("raw-preview")).toBeVisible();
  await page.getByRole("button", { name: "Start analysis" }).click();
  await expect(page).toHaveURL(/\/s\/[0-9a-f-]{36}\/health$/);
  await page.goto(page.url().replace(/\/health$/, "/dashboard"));
  await expect(page.getByTestId("widget").first()).toBeVisible();
}

const widget = (page: Page, title: string) => page.getByRole("region", { name: title, exact: true });

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

test("automatic dashboard shows figures calculated from the uploaded data", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await openDashboard(page);
  await expect(page.getByTestId("auto-note")).toContainText("Built automatically from your column types");
  await expect(page.getByTestId("widget")).toHaveCount(10); // 4 KPI cards + 6 charts

  await expect(widget(page, "Rows").getByTestId("kpi-value")).toContainText("60");
  const sum = widget(page, "Sum of Amount");
  await expect(sum.getByTestId("kpi-value")).toContainText("19.3K");
  await expect(sum.getByTestId("kpi-value")).toContainText("exactly 19,260");
  await expect(sum.getByTestId("kpi-value")).toContainText("From 58 usable values");
  await expect(sum.getByTestId("widget-notes")).toContainText("2 rows have no value in “Amount” and are not counted as zero.");
  await expect(widget(page, "Average of Amount").getByTestId("kpi-value")).toContainText("332.07");

  const byRegion = widget(page, "Sum of Amount by Region");
  await expect(byRegion.getByTestId("widget-summary")).toContainText("Highest: South (6,780). Lowest: North (5,710).");
  await expect(byRegion.getByRole("img")).toHaveAttribute("aria-label", /3 groups/);
  await expect(byRegion.locator("svg.recharts-surface")).toBeVisible();
  await expect(page.getByTestId("save-state")).toContainText("Saved");

  // the same figures as an accessible table
  await byRegion.getByRole("button", { name: "Show as table" }).click();
  const table = byRegion.getByTestId("chart-table");
  await expect(table.getByRole("row")).toHaveCount(4);
  await expect(table.getByRole("row").nth(1)).toContainText("South");
  await expect(table.getByRole("row").nth(1)).toContainText("6,780");
  await byRegion.getByRole("button", { name: "Show as chart" }).click();

  await noHorizontalScroll(page);
  expect(errors).toEqual([]);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/dashboard-${info.project.name}.png`, fullPage: true });
});

test("filters apply to every widget and can be removed", async ({ page }) => {
  await openDashboard(page);
  await page.getByRole("button", { name: "Add filter" }).click();
  const dialog = page.getByTestId("filter-dialog");
  await dialog.getByLabel("Column").selectOption("Region");
  await expect(dialog.getByRole("button", { name: "Apply filter" })).toBeDisabled(); // nothing ticked yet
  await dialog.getByRole("checkbox", { name: "North" }).click();
  await dialog.getByRole("button", { name: "Apply filter" }).click();

  await expect(page.getByTestId("filter-chip")).toHaveText(/Region is North/);
  await expect(page.getByTestId("filter-count")).toHaveText("20 of 60 rows match");
  await expect(widget(page, "Rows").getByTestId("kpi-value")).toContainText("20");
  await expect(widget(page, "Sum of Amount").getByTestId("kpi-value")).toContainText("5,710");
  await expect(widget(page, "Sum of Amount by Region").getByTestId("widget-summary")).toContainText("1 group. North: 5,710.");

  // a number range on top
  await page.getByRole("button", { name: "Add filter" }).click();
  await dialog.getByLabel("Column").selectOption("Amount");
  await dialog.getByLabel("Minimum").fill("900");
  await dialog.getByLabel("Maximum").fill("100");
  await expect(dialog.getByRole("status")).toHaveText("The minimum is greater than the maximum.");
  await dialog.getByLabel("Minimum").fill("100000");
  await dialog.getByLabel("Maximum").fill("");
  await dialog.getByRole("button", { name: "Apply filter" }).click();
  await expect(page.getByTestId("filter-count")).toHaveText("0 of 60 rows match");
  await expect(widget(page, "Sum of Amount by Region").getByTestId("widget-empty")).toHaveText("No rows match the current filters.");
  await expect(widget(page, "Sum of Amount").getByTestId("widget-empty")).toHaveText("No rows match the current filters."); // not 0

  await page.getByRole("button", { name: "Clear all" }).click();
  await expect(page.getByTestId("filter-chip")).toHaveCount(0);
  await expect(widget(page, "Rows").getByTestId("kpi-value")).toContainText("60");
});

test("selecting a bar filters the dashboard (drill-down)", async ({ page }) => {
  await openDashboard(page);
  const byRegion = widget(page, "Sum of Amount by Region");
  await byRegion.locator(".recharts-bar-rectangle").first().click(); // largest first: South
  await expect(page.getByTestId("filter-chip")).toHaveText(/Region is South/);
  await expect(widget(page, "Rows").getByTestId("kpi-value")).toContainText("20");
  await expect(widget(page, "Sum of Amount").getByTestId("kpi-value")).toContainText("6,780");
  await page.getByRole("button", { name: "Remove filter: Region is South" }).click();
  await expect(widget(page, "Rows").getByTestId("kpi-value")).toContainText("60");
});

test("add, edit, move and remove widgets; layout and theme are saved", async ({ page }) => {
  await openDashboard(page);
  await page.getByRole("button", { name: "Add widget" }).click();
  const editor = page.getByTestId("widget-editor");
  await editor.getByLabel("Chart type").selectOption("kpi");
  await editor.getByLabel("Value").selectOption("Region");
  // only valid calculations are offered for a text column
  await expect(editor.getByLabel("Calculation").locator("option")).toHaveText(["Count", "Distinct count"]);
  await editor.getByLabel("Calculation").selectOption("distinct");
  await expect(editor.getByTestId("editor-preview").getByTestId("kpi-value")).toContainText("3");
  await expect(editor.getByLabel("Title")).toHaveValue("Distinct count of Region");
  await editor.getByRole("button", { name: "Add to dashboard" }).click();
  await expect(page.getByTestId("widget")).toHaveCount(11);
  await expect(widget(page, "Distinct count of Region").getByTestId("kpi-value")).toContainText("3");

  await page.getByRole("button", { name: "Customize" }).click();
  await page.getByRole("button", { name: "Edit Distinct count of Region" }).click();
  await editor.getByLabel("Chart type").selectOption("bar");
  await editor.getByLabel("Value").selectOption("Units");
  await editor.getByLabel("Calculation").selectOption("median");
  await editor.getByLabel("Group by").selectOption("Channel");
  await editor.getByLabel("Title").fill("Typical units per channel");
  await expect(editor.getByTestId("editor-preview").locator(".recharts-bar-rectangle")).toHaveCount(2);
  await editor.getByRole("button", { name: "Save changes" }).click();
  const mine = widget(page, "Typical units per channel");
  await expect(mine.getByTestId("widget-summary")).toContainText("Median of Units by Channel, 2 groups");

  const ids = () => page.getByTestId("widget").evaluateAll((els) => els.map((e) => e.getAttribute("data-widget-id")));
  const before = await ids();
  await page.getByRole("button", { name: "Move earlier" }).last().click();
  const after = await ids();
  expect(after.at(-2)).toBe(before.at(-1));
  await page.getByRole("button", { name: "Remove Rows", exact: true }).click();
  await expect(page.getByTestId("widget")).toHaveCount(10);
  await page.getByRole("button", { name: "Done" }).click();

  await page.getByLabel("Dashboard theme").selectOption("midnight");
  await expect(page.getByTestId("dashboard-canvas")).toHaveAttribute("data-theme-id", "midnight");
  await expect(page.getByTestId("save-state")).toContainText("Saved");

  await page.reload();
  await expect(page.getByTestId("dashboard-canvas")).toHaveAttribute("data-theme-id", "midnight");
  await expect(page.getByTestId("widget")).toHaveCount(10);
  await expect(widget(page, "Typical units per channel")).toBeVisible();
  await expect(page.getByTestId("auto-note")).toHaveCount(0); // a saved dashboard is not presented as automatic
  expect(await ids()).toEqual(after.filter((id) => id !== before[0]));
});

test("chart image download and rebuild confirmation", async ({ page }) => {
  await openDashboard(page);
  const byRegion = widget(page, "Sum of Amount by Region");
  const download = page.waitForEvent("download");
  await byRegion.getByRole("button", { name: "Save chart as image" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("Sum-of-Amount-by-Region.png");

  await page.getByRole("button", { name: "Customize" }).click();
  await page.getByRole("button", { name: "Remove Sum of Amount by Region" }).click();
  await expect(page.getByTestId("widget")).toHaveCount(9);
  await page.getByRole("button", { name: "Rebuild automatically" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("replaces all 9 widgets");
  await page.getByRole("alertdialog").getByRole("button", { name: "Rebuild" }).click();
  await expect(page.getByTestId("widget")).toHaveCount(10);
});
