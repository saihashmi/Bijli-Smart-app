import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const FIX = path.join(__dirname, "fixtures");
const SHOTS = process.env.SCREENSHOT_DIR;

async function openExport(page: Page) {
  await page.goto("/upload");
  await page.getByTestId("file-input").setInputFiles(path.join(FIX, "sales_small.xlsx"));
  await expect(page.getByTestId("raw-preview")).toBeVisible();
  await page.getByRole("button", { name: "Start analysis" }).click();
  await expect(page).toHaveURL(/\/s\/[0-9a-f-]{36}\/health$/);
  await page.goto(page.url().replace(/\/health$/, "/export"));
  await expect(page.getByTestId("export-center")).toBeVisible();
}

test("create and download an Excel workbook and a PDF report", async ({ page }, info) => {
  await openExport(page);
  await expect(page.getByText("No exports yet")).toBeVisible();

  await page.getByRole("button", { name: "Create Excel workbook" }).click();
  const jobs = page.getByTestId("export-job");
  await expect(jobs).toHaveCount(1);
  await expect(jobs.first()).toHaveAttribute("data-status", "done");
  await expect(jobs.first()).toContainText("sales_small - cleaned.xlsx");
  await expect(jobs.first()).toContainText("60 rows × 6 columns");
  await expect(jobs.first()).toContainText("Deleted automatically on");

  const xlsx = page.waitForEvent("download");
  await jobs.first().getByRole("button", { name: "Download" }).click();
  const file = await xlsx;
  expect(file.suggestedFilename()).toBe("sales_small - cleaned.xlsx");
  expect(await file.failure()).toBeNull();

  await page.getByRole("button", { name: "Create PDF report" }).click();
  await expect(jobs).toHaveCount(2);
  await expect(jobs.first()).toContainText("sales_small - report.pdf");
  await expect(jobs.first()).toContainText(/\d+ pages?/);
  const pdf = page.waitForEvent("download");
  await jobs.first().getByRole("button", { name: "Download" }).click();
  expect((await pdf).suggestedFilename()).toBe("sales_small - report.pdf");
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/export-${info.project.name}.png`, fullPage: true });

  await page.getByRole("button", { name: "Delete export sales_small - report.pdf" }).click();
  await expect(jobs).toHaveCount(1);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
