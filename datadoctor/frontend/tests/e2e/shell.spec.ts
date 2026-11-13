import { expect, test, type Page } from "@playwright/test";

const SHOTS = process.env.SCREENSHOT_DIR;

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "page scrolls sideways").toBeLessThanOrEqual(0);
}

const isDesktop = (page: Page) => (page.viewportSize()?.width ?? 0) >= 1024;

test("landing page explains the product and links into the app", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Your Data Has Potential.");
  await expect(page.getByRole("heading", { name: "From upload to answer in five steps" })).toBeVisible();
  await expect(page.getByText("Synthetic example data")).toBeVisible();
  await expect(page.getByTestId("footer-version")).toHaveText(/Version \d+\.\d+\.\d+/);
  await noHorizontalScroll(page);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/landing-${info.project.name}.png`, fullPage: true });

  await page.getByRole("link", { name: "Explore Features" }).click();
  await expect(page).toHaveURL(/#features$/);
  await expect(page.locator("#features")).toBeInViewport(); // let the smooth scroll finish before the next click
  await page.getByRole("link", { name: "Launch DataDoctor AI" }).click();
  await expect(page).toHaveURL(/\/upload$/);
  await page.goBack(); // regression: Back after a section link must return to the landing page
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Your Data Has Potential.");
  await page.getByRole("link", { name: "Start Analyzing" }).click();
  await expect(page).toHaveURL(/\/upload$/);
  await expect(page.getByRole("heading", { name: "Upload Studio" })).toBeVisible();
  expect(errors, errors.join("\n")).toEqual([]);
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
    await expect(scope.locator('[aria-disabled="true"]').filter({ hasText: label })).toHaveCount(1);
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

test("sidebar collapses and remembers it", async ({ page }) => {
  test.skip(!isDesktop(page), "the collapsible sidebar exists on desktop widths only");
  await page.goto("/workspace");
  const sidebar = page.getByTestId("sidebar");
  const wide = (await sidebar.boundingBox())!.width;
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect.poll(async () => (await sidebar.boundingBox())!.width).toBeLessThan(wide / 2);
  await page.reload();
  await expect(page.getByRole("button", { name: "Expand sidebar" })).toBeVisible();
  // Collapsed items are still reachable links with accessible names.
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Settings" }).click();
  await expect(page).toHaveURL(/\/settings$/);
});

test("command palette: open with the keyboard, search, run a command", async ({ page }) => {
  await page.goto("/workspace");
  await page.keyboard.press("Control+k");
  const input = page.getByRole("combobox", { name: "Search commands" });
  await expect(input).toBeFocused();
  await input.fill("sett");
  await expect(page.getByRole("option")).toHaveCount(1);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/settings$/);

  await page.keyboard.press("Control+k");
  await page.getByRole("combobox", { name: "Search commands" }).fill("dark");
  await page.keyboard.press("Enter");
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
});
