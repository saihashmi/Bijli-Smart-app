import { expect, test } from "@playwright/test";

test("home page loads and reaches the real backend", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "DataDoctor AI" })).toBeVisible();
  await expect(page.getByTestId("backend-status")).toContainText("Backend connected");
});
