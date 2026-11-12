import { expect, test, type Page } from "@playwright/test";

const SHOTS = process.env.SCREENSHOT_DIR;

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "page scrolls sideways").toBeLessThanOrEqual(0);
}

const isDesktop = (page: Page) => (page.viewportSize()?.width ?? 0) >= 1024;

test("landing page explains the product and links into the app", async ({ page }, info) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("From Messy Data to");
  await expect(page.getByRole("heading", { name: "How it works" })).toBeVisible();
  await expect(page.getByText("Illustration")).toBeVisible();
  await noHorizontalScroll(page);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/landing-${info.project.name}.png`, fullPage: true });
  await page.getByRole("link", { name: "Upload a spreadsheet" }).first().click();
  await expect(page).toHaveURL(/\/upload$/);
  await expect(page.getByRole("heading", { name: "Upload Studio" })).toBeVisible();
});

test("app navigation works on every screen size", async ({ page }, info) => {
  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "Workspace", level: 1 })).toBeVisible();
  await expect(page.getByText("Local mode").first()).toBeVisible();
  await noHorizontalScroll(page);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/workspace-${info.project.name}.png`, fullPage: true });

  if (isDesktop(page)) {
    const nav = page.getByRole("navigation", { name: "Main" });
    await nav.getByRole("link", { name: "Settings" }).click();
  } else {
    await page.getByRole("button", { name: "Open navigation menu" }).click();
    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();
    if (SHOTS) {
      await expect.poll(async () => (await drawer.boundingBox())?.x).toBe(0); // wait for the slide-in to finish
      await page.screenshot({ path: `${SHOTS}/drawer-${info.project.name}.png` });
    }
    await drawer.getByRole("link", { name: "Settings" }).click();
    await expect(drawer).toBeHidden();
  }
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
  await expect(page.getByTestId("backend-status")).toContainText("Backend connected");
  await noHorizontalScroll(page);
});

test("dataset tools are disabled until a dataset is open", async ({ page }) => {
  await page.goto("/workspace");
  if (!isDesktop(page)) await page.getByRole("button", { name: "Open navigation menu" }).click();
  const scope = isDesktop(page) ? page.getByRole("navigation", { name: "Main" }) : page.getByRole("dialog");
  for (const label of ["Data Health", "Cleaning Studio", "Dashboard Studio", "AI Analyst", "Export Center"]) {
    await expect(scope.getByRole("link", { name: label })).toHaveCount(0);
    await expect(scope.getByText(label)).toHaveAttribute("aria-disabled", "true");
  }
});

test("theme switch applies and persists across reloads", async ({ page }) => {
  await page.goto("/settings");
  const group = page.getByRole("main").getByRole("radiogroup", { name: "Colour theme" });
  await group.getByRole("radio", { name: "Dark" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(page.getByRole("main").getByRole("radio", { name: "Dark" })).toHaveAttribute("aria-checked", "true");
  await page.getByRole("main").getByRole("radio", { name: "Light" }).click();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
});

test("skip link moves focus to the main content", async ({ page }) => {
  await page.goto("/workspace");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main$/);
});
