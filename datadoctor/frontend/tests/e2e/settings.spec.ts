import { expect, test } from "@playwright/test";

test("settings load from the server with SPEC defaults", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByLabel("Display time zone")).toHaveValue("Asia/Karachi");
  await expect(page.getByLabel("Date display format")).toHaveValue("DD/MM/YYYY");
  await expect(page.getByText("Uploaded files deleted after")).toBeVisible();
  await expect(page.getByText("7 days")).toBeVisible();
  await expect(page.getByText("20 MB")).toBeVisible();
  await expect(page.getByText("Not configured")).toBeVisible();
  await expect(page.getByTestId("backend-status")).toContainText("Database: OK · Storage: OK");
});

test("preferences save, persist across reloads and stay per-browser", async ({ page, browser }) => {
  await page.goto("/settings");
  await page.getByLabel("Date display format").selectOption("YYYY-MM-DD");
  await expect(page.getByText("Setting saved").first()).toBeVisible();
  await expect(page.getByTestId("date-preview")).toContainText(/\d{4}-\d{2}-\d{2}/);

  const share = page.getByRole("switch", { name: "Share column names with AI" });
  await expect(share).toHaveAttribute("aria-checked", "true");
  await share.click();
  await expect(share).toHaveAttribute("aria-checked", "false");

  await page.reload();
  await expect(page.getByLabel("Date display format")).toHaveValue("YYYY-MM-DD");
  await expect(page.getByRole("switch", { name: "Share column names with AI" })).toHaveAttribute("aria-checked", "false");

  // A different browser (new cookie jar) gets its own workspace with defaults.
  const other = await browser.newContext();
  const otherPage = await other.newPage();
  await otherPage.goto(page.url());
  await expect(otherPage.getByLabel("Date display format")).toHaveValue("DD/MM/YYYY");
  await other.close();
});

test("delete all data asks for confirmation first", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("button", { name: "Delete all data" }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toContainText("cannot be undone");
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(dialog).toBeHidden();

  await page.getByRole("button", { name: "Delete all data" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Delete everything" }).click();
  await expect(page.getByText("There was no stored data to delete.")).toBeVisible();
});
