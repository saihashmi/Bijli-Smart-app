import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const FIX = path.join(__dirname, "fixtures");
const SHOTS = process.env.SCREENSHOT_DIR;
const isDesktop = (page: Page) => (page.viewportSize()?.width ?? 0) >= 1024;

async function openSession(page: Page, file: string) {
  await page.goto("/upload");
  await page.getByTestId("file-input").setInputFiles(path.join(FIX, file));
  await expect(page.getByTestId("raw-preview")).toBeVisible();
  await page.getByRole("button", { name: "Start analysis" }).click();
  await expect(page).toHaveURL(/\/s\/[0-9a-f-]{36}\/health$/);
}

test("profiles every column with exact counts", async ({ page }, info) => {
  await openSession(page, "invoices_quality.xlsx");
  const kpis = page.getByTestId("health-kpis");
  await expect(kpis).toContainText("8 columns");
  await expect(kpis).toContainText("Exact duplicate rows1");
  await expect(kpis).toContainText("1 completely empty row");

  await expect(page.getByText("How the sheet was read")).toBeVisible();
  await expect(page.getByText("blank header named “Column 6”")).toBeVisible();
  await expect(page.getByText("duplicate header “Amount” renamed “Amount (2)”")).toBeVisible();
  await expect(page.getByText(/1 cell\(s\) contain Excel errors/)).toBeVisible();

  const cards = page.getByTestId("column-card");
  await expect(cards).toHaveCount(8);
  const date = cards.filter({ hasText: /^Date/ });
  await expect(date).toContainText("1 ambiguous date (DD/MM or MM/DD)");
  await expect(date).toContainText("1 invalid date");
  const amount = cards.filter({ has: page.getByRole("heading", { name: "Amount", exact: true }) });
  await expect(amount).toContainText("Number");
  await expect(amount).toContainText("numbers stored as text");
  await expect(cards.filter({ has: page.getByRole("heading", { name: "Paid" }) })).toContainText("Yes / No");
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/health-${info.project.name}.png`, fullPage: true });

  await page.getByLabel("Filter columns").fill("city");
  await expect(cards).toHaveCount(1);
});

test("data preview loads pages while scrolling", async ({ page }, info) => {
  await openSession(page, "squares_1200.xlsx");
  await page.getByRole("tab", { name: "Data preview" }).click();
  const grid = page.getByTestId("data-grid");
  await expect(grid.getByRole("gridcell", { name: "1", exact: true }).first()).toBeVisible();
  await expect(grid.getByRole("columnheader", { name: /square/ })).toBeVisible();
  // Fewer DOM rows than data rows: the grid is virtualised.
  expect(await grid.getByRole("row").count()).toBeLessThan(100);
  await grid.evaluate((el) => el.scrollTo({ top: el.scrollHeight }));
  await expect(grid.getByRole("gridcell", { name: "1440000", exact: true })).toBeVisible(); // row 1200 = 1200²
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/grid-${info.project.name}.png` });
});

test("session tools become available in the navigation", async ({ page }) => {
  await openSession(page, "legacy_claims.xls");
  const sessionUrl = page.url();
  if (!isDesktop(page)) await page.getByRole("button", { name: "Open navigation menu" }).click();
  const nav = isDesktop(page) ? page.getByRole("navigation", { name: "Main" }) : page.getByRole("dialog");
  await nav.getByRole("link", { name: "Cleaning Studio" }).click();
  await expect(page.getByRole("heading", { name: "Cleaning Studio", level: 1 })).toBeVisible();
  await expect(page.getByTestId("coming-soon")).toContainText("Milestone 7");
  await expect(page.getByTestId("session-file")).toHaveText("legacy_claims.xls");

  // The last session is remembered on other pages.
  await page.goto("/settings");
  if (!isDesktop(page)) await page.getByRole("button", { name: "Open navigation menu" }).click();
  const nav2 = isDesktop(page) ? page.getByRole("navigation", { name: "Main" }) : page.getByRole("dialog");
  await expect(nav2.getByRole("link", { name: "Data Health" })).toHaveAttribute("href", new URL(sessionUrl).pathname);
});

test("unknown or foreign sessions show a clear message", async ({ page }) => {
  await page.goto("/s/00000000-0000-4000-8000-000000000000/health");
  await expect(page.getByTestId("session-error")).toContainText("This analysis session is not available");
  await page.getByRole("link", { name: "Go to Workspace" }).click();
  await expect(page).toHaveURL(/\/workspace$/);
});
