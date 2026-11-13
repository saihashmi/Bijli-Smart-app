import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const FIX = path.join(__dirname, "fixtures");
const SHOTS = process.env.SCREENSHOT_DIR;

async function chooseFile(page: Page, file: string | { name: string; mimeType: string; buffer: Buffer }) {
  await page.getByTestId("file-input").setInputFiles(typeof file === "string" ? path.join(FIX, file) : file);
}

test("empty workspace invites an upload", async ({ page }) => {
  await page.goto("/workspace");
  await expect(page.getByTestId("workspace-empty")).toContainText("No datasets yet");
});

test("upload a multi-sheet workbook, pick sheet and header row, start a session", async ({ page }, info) => {
  await page.goto("/upload");
  await chooseFile(page, "multi_sheet_sales.xlsx");

  await expect(page.getByRole("heading", { name: /multi_sheet_sales\.xlsx/ })).toBeVisible();
  await expect(page.getByText("4 sheets found, including hidden ones.")).toBeVisible();
  await expect(page.getByTestId("sheet-option-1")).toContainText("Hidden");
  await expect(page.getByTestId("sheet-option-2")).toContainText("Very hidden");
  await expect(page.getByTestId("sheet-option-3")).toContainText("This sheet is empty.");
  await expect(page.getByTestId("sheet-option-0")).toContainText("2 formula cells have no saved result");
  await expect(page.getByTestId("sheet-option-2")).toContainText("1 row × 1 column");
  await expect(page.getByText("'Chart' is a chart sheet and has no table data.")).toBeVisible();
  await expect(page.getByRole("radio", { name: /Empty/ })).toBeDisabled();

  const preview = page.getByTestId("raw-preview");
  await expect(preview).toContainText("Monthly sales report");
  await expect(preview).toContainText("Rs 1,000"); // raw value, not converted
  await page.getByLabel("Column names are in").selectOption({ label: "Row 2" });
  await expect(preview.getByRole("row", { name: "Row 2, header row" })).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/upload-ready-${info.project.name}.png`, fullPage: true });

  await page.getByRole("button", { name: "Start analysis" }).click();
  // Real stages: each one completes only when its request returns.
  const stages = page.getByTestId("stage-list").last();
  await expect(stages.locator('[data-stage="read"]')).toHaveAttribute("data-status", /active|done/);
  await expect(page).toHaveURL(/\/s\/[0-9a-f-]{36}\/health$/);
  await expect(page.getByTestId("session-file")).toHaveText("multi_sheet_sales.xlsx");
  await expect(page.getByTestId("health-score")).toBeVisible(); // profile was already computed during the stages

  await page.goto("/workspace");
  const card = page.getByTestId("dataset-card").first();
  await expect(card).toContainText("multi_sheet_sales.xlsx");
  await expect(card).toContainText("Sales");
  await expect(card).toContainText("header on row 2");
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/workspace-${info.project.name}.png`, fullPage: true });
});

test("hidden sheets can be selected and previewed", async ({ page }) => {
  await page.goto("/upload");
  await chooseFile(page, "multi_sheet_sales.xlsx");
  await page.getByTestId("sheet-option-1").click();
  await expect(page.getByTestId("raw-preview")).toContainText("Code");
});

test("CSV encoding and delimiter are detected", async ({ page }) => {
  await page.goto("/upload");
  const csv = "Name;City;Amount\nZoë;Lahore;1.250,50\nBilal;Karachi;900\n";
  await chooseFile(page, { name: "semicolon.csv", mimeType: "text/csv", buffer: Buffer.from(csv, "utf-8") });
  await expect(page.getByText("semicolon", { exact: true })).toBeVisible();
  await expect(page.getByText("UTF-8", { exact: true })).toBeVisible();
  await expect(page.getByTestId("raw-preview")).toContainText("Zoë");
});

test("legacy .xls workbooks are supported", async ({ page }) => {
  await page.goto("/upload");
  await chooseFile(page, "legacy_claims.xls");
  await expect(page.getByText("Excel 97–2003 workbook")).toBeVisible();
  await expect(page.getByTestId("raw-preview")).toContainText("C-001");
});

test("drag and drop works", async ({ page }) => {
  await page.goto("/upload");
  const dataTransfer = await page.evaluateHandle(() => {
    const dt = new DataTransfer();
    dt.items.add(new File(["a,b\n1,2\n"], "dropped.csv", { type: "text/csv" }));
    return dt;
  });
  await page.getByRole("button", { name: /Drop your spreadsheet here/ }).dispatchEvent("drop", { dataTransfer });
  await expect(page.getByRole("heading", { name: /dropped\.csv/ })).toBeVisible();
});

test("password-protected and unsupported files show clear errors", async ({ page }) => {
  await page.goto("/upload");
  await chooseFile(page, "password_protected.xlsx");
  await expect(page.getByRole("alert").filter({ hasText: "password-protected" })).toBeVisible();

  await chooseFile(page, { name: "report.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7") });
  await expect(page.getByRole("alert").filter({ hasText: "Unsupported file type" })).toBeVisible();

  // Server-side content check: a PDF disguised as .xlsx.
  await chooseFile(page, { name: "disguised.xlsx", mimeType: "application/octet-stream", buffer: Buffer.from("%PDF-1.7 fake") });
  await expect(page.getByRole("alert").filter({ hasText: "PDF document" })).toBeVisible();
});

test("resume setup and delete a dataset with confirmation", async ({ page }) => {
  await page.goto("/upload");
  await chooseFile(page, "legacy_claims.xls");
  await expect(page.getByTestId("raw-preview")).toBeVisible();
  await page.goto("/workspace");
  const card = page.getByTestId("dataset-card");
  await expect(card).toContainText("Setup not finished");

  await card.getByRole("link", { name: "Continue setup" }).click();
  await expect(page).toHaveURL(/\/upload\?dataset=/);
  await expect(page.getByTestId("raw-preview")).toContainText("C-001");

  await page.goto("/workspace");
  await page.getByRole("button", { name: "Delete legacy_claims.xls" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Delete" }).click();
  await expect(page.getByTestId("workspace-empty")).toBeVisible();
});

test("regression: files between 10 MB and the 20 MB limit pass through the proxy; larger ones get a clean 413", async ({ page }) => {
  // Next.js truncates proxied bodies over 10 MB unless configured (found in Milestone 4).
  const row = "2026-01-01,Lahore,Product,12,1250.50\n";
  const big = Buffer.from("date,city,product,qty,amount\n" + row.repeat(Math.floor((19 * 1024 * 1024) / row.length)));
  await page.goto("/upload");
  await chooseFile(page, { name: "nineteen-mb.csv", mimeType: "text/csv", buffer: big });
  await expect(page.getByTestId("raw-preview")).toContainText("Lahore", { timeout: 30_000 });

  const tooBig = Buffer.alloc(21 * 1024 * 1024, "a");
  const res = await page.request.post("/api/uploads", {
    multipart: { file: { name: "too-big.csv", mimeType: "text/csv", buffer: tooBig } },
  });
  expect(res.status()).toBe(413);
  expect((await res.json()).error.code).toBe("FILE_TOO_LARGE");
});
