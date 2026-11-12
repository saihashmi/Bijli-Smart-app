import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const FIX = path.join(__dirname, "fixtures");
const SHOTS = process.env.SCREENSHOT_DIR;

async function openSession(page: Page, file = "invoices_quality.xlsx") {
  await page.goto("/upload");
  await page.getByTestId("file-input").setInputFiles(path.join(FIX, file));
  await expect(page.getByTestId("raw-preview")).toBeVisible();
  await page.getByRole("button", { name: "Start analysis" }).click();
  await expect(page).toHaveURL(/\/s\/[0-9a-f-]{36}\/health$/);
  return page.url().replace(/\/health$/, "");
}

async function pickTool(page: Page, title: string) {
  const desktop = (page.viewportSize()?.width ?? 0) >= 1024;
  if (desktop) await page.getByRole("navigation", { name: "Cleaning tools" }).getByRole("button", { name: title }).click();
  else await page.getByLabel("Choose a cleaning tool").selectOption({ label: title });
}

test("fix an issue from the Data Health Center with preview and apply", async ({ page }, info) => {
  await openSession(page);
  const issue = page.getByTestId("issue").filter({ hasText: "Leading or trailing spaces" });
  await issue.getByRole("link", { name: "Fix in Cleaning Studio" }).click();
  await expect(page).toHaveURL(/\/clean\?op=trim_whitespace&column=City/);
  await expect(page.getByRole("checkbox", { name: "City" })).toBeChecked();

  await page.getByRole("button", { name: "Preview on full data" }).click();
  const preview = page.getByTestId("op-preview");
  await expect(preview).toContainText("1 row affected");
  await expect(preview.getByRole("cell", { name: /lahore/ })).toBeVisible();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/clean-preview-${info.project.name}.png`, fullPage: true });
  await page.getByRole("button", { name: "Apply change" }).click();
  await expect(page.getByText(/Trim whitespace: Leading and trailing spaces removed/)).toBeVisible();
  await expect(page.getByText("Cleaned · v1")).toBeVisible();
  await page.getByRole("tab", { name: /Applied changes/ }).click();
  await expect(page.getByTestId("history")).toContainText("#1");
});

test("merge category spellings", async ({ page }) => {
  const base = await openSession(page);
  await page.goto(`${base}/clean`);
  await pickTool(page, "Normalise category labels");
  await page.getByLabel("Column", { exact: true }).selectOption("City");
  const mapping = page.getByTestId("category-mapping");
  await expect(mapping.getByLabel("Use this label")).toHaveValue("Lahore");
  await page.getByRole("button", { name: "Preview on full data" }).click();
  await expect(page.getByTestId("op-preview")).toContainText("2 rows affected");
  await page.getByRole("button", { name: "Apply change" }).click();
  await expect(page.getByText("Cleaned · v1")).toBeVisible();
});

test("destructive changes ask for confirmation and keep original row numbers", async ({ page }) => {
  const base = await openSession(page);
  await page.goto(`${base}/clean?op=remove_exact_duplicates`);
  await page.getByRole("button", { name: "Preview on full data" }).click();
  await expect(page.getByTestId("op-preview")).toContainText("Removed");
  await page.getByRole("button", { name: "Apply change" }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toContainText("1 row(s) will be removed");
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByText("Original data")).toBeVisible(); // nothing applied
  await page.getByRole("button", { name: "Apply change" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Yes, apply" }).click();
  await expect(page.getByTestId("session-file").locator("..").locator("..")).toContainText("7 rows");
  const grid = page.getByTestId("data-grid");
  await expect(grid.getByRole("rowheader", { name: "7", exact: true })).toBeVisible();
  await expect(grid.getByRole("rowheader", { name: "6", exact: true })).toHaveCount(0);
  await page.getByRole("tab", { name: "Original" }).click();
  await expect(page.getByRole("grid", { name: "Original data" }).getByRole("rowheader", { name: "6", exact: true })).toBeVisible();
});

test("ambiguous dates need an explicit reading and failures are reported", async ({ page }, info) => {
  const base = await openSession(page);
  await page.goto(`${base}/clean?op=normalize_dates&column=Date`);
  const chooser = page.getByTestId("date-interpretation");
  await expect(chooser).toContainText("1 value(s) only make sense day-first");
  await expect(chooser).toContainText("1 ambiguous");
  await expect(chooser.getByRole("radio", { name: /Day first/ })).toBeChecked(); // evidence supports DD/MM
  await page.getByRole("button", { name: "Preview on full data" }).click();
  await expect(page.getByTestId("failure-report")).toContainText("1 value(s) could not be converted");
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/clean-dates-${info.project.name}.png`, fullPage: true });
  await page.getByTestId("failure-report").locator("summary").click();
  await expect(page.getByTestId("failure-report")).toContainText("31/02/2026");
  await page.getByRole("button", { name: "Apply change" }).click();
  await expect(page.getByText("Cleaned · v1")).toBeVisible();

  await page.goto(`${base}/health`);
  await expect(page.getByTestId("issue").filter({ hasText: "Ambiguous dates" })).toHaveCount(0);
});

test("missing values are never filled without an explicit value", async ({ page }) => {
  const base = await openSession(page);
  await page.goto(`${base}/clean?op=handle_missing&column=Amount`);
  await page.getByLabel("What to do").selectOption("fixed");
  await page.getByRole("button", { name: "Preview on full data" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Enter the value to fill missing cells with." })).toBeVisible();
  await page.getByLabel("Fill value").fill("0");
  await page.getByRole("button", { name: "Preview on full data" }).click();
  await expect(page.getByTestId("op-preview")).toContainText("filled with the value “0”");
});
