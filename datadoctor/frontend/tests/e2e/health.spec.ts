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
  await expect(page.getByTestId("issue-kpi")).toContainText(/\d+ high · \d+ medium · \d+ low/);
  await expect(kpis).toContainText("Exact duplicate rows1");
  await expect(kpis).toContainText("1 completely empty row");

  await expect(page.getByText("How the sheet was read")).toBeVisible();
  await expect(page.getByText("blank header named “Column 6”")).toBeVisible();
  await expect(page.getByText("duplicate header “Amount” renamed “Amount (2)”")).toBeVisible();
  await expect(page.getByText(/1 cell\(s\) contain Excel errors/)).toBeVisible();

  await page.getByRole("tab", { name: "Column profiles" }).click();
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

test("health score and issue list", async ({ page }, info) => {
  await openSession(page, "invoices_quality.xlsx");
  const score = page.getByTestId("score-card");
  await expect(page.getByTestId("health-score")).toHaveText(/^\d{1,3}$/);
  await expect(score).toContainText("Completeness");
  await expect(score).toContainText("Format consistency");
  await score.getByText("How is this calculated?").click();
  await expect(score).toContainText("0.35 × Completeness");
  await expect(score).toContainText("does not check whether values are true");

  await expect(page.getByTestId("missing-chart")).toContainText("Notes");
  const issues = page.getByTestId("issue");
  await expect(issues.first()).toContainText("High");
  await expect(issues.filter({ hasText: "Ambiguous dates" })).toContainText("could mean 3 April or 4 March");
  await expect(issues.filter({ hasText: "Exact duplicate rows" })).toContainText("Row");
  await expect(issues.filter({ hasText: "Inconsistent category labels" })).toContainText("“Lahore” (1)");
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/issues-${info.project.name}.png`, fullPage: true });

  const total = await issues.count();
  await page.getByRole("radio", { name: /^High/ }).click();
  const high = await issues.count();
  expect(high).toBeGreaterThan(0);
  expect(high).toBeLessThan(total);
  for (const badge of await issues.locator("[data-slot=badge]").first().allTextContents()) expect(badge).toBe("High");
  await page.getByRole("radio", { name: /^All/ }).click();
  await page.getByLabel("Filter by column").selectOption("Date");
  await expect(issues.filter({ hasText: "Exact duplicate rows" })).toHaveCount(0);
  await expect(issues.filter({ hasText: "Invalid dates" })).toHaveCount(1);
});

test("personal information is flagged and can be marked sensitive", async ({ page }) => {
  const csv = "Customer Name,CNIC,Amount\nAyesha,35202-1234567-1,100\nBilal,42101-7654321-3,200\nSana,61101-1111111-5,300\n";
  await page.goto("/upload");
  await page.getByTestId("file-input").setInputFiles({ name: "people.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await expect(page.getByTestId("raw-preview")).toBeVisible();
  await page.getByRole("button", { name: "Start analysis" }).click();
  const pii = page.getByTestId("issue").filter({ hasText: "Possible personal information" });
  await expect(pii).toHaveCount(2);
  await expect(pii.filter({ hasText: "CNIC" })).not.toContainText("1234567"); // examples are masked
  await pii.filter({ hasText: "CNIC" }).getByRole("button", { name: "Mark as sensitive" }).click();
  await expect(page.getByText("“CNIC” marked as sensitive")).toBeVisible();
  await expect(pii).toHaveCount(1);

  await page.getByRole("tab", { name: "Column profiles" }).click();
  await expect(page.getByRole("button", { name: "Sensitive column CNIC" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Not sensitive column Customer Name" }).click();
  await expect(page.getByRole("button", { name: "Sensitive column Customer Name" })).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await page.getByRole("tab", { name: "Column profiles" }).click();
  await expect(page.getByRole("button", { name: "Sensitive column Customer Name" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("tab", { name: /Issues/ }).click();
  await expect(page.getByTestId("issue").filter({ hasText: "Possible personal information" })).toHaveCount(0);
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
