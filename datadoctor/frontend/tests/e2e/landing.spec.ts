import { expect, test } from "@playwright/test";

const hero = "[data-testid=hero-visual]";

test("3D hero loads after the headline and never blocks navigation", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  // Headline and CTA are usable before any 3D code has arrived.
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Start Analyzing" })).toBeEnabled();
  await expect(page.locator(hero)).toHaveAttribute("data-hero-mode", "3d", { timeout: 20_000 });
  await expect(page.locator(`${hero} canvas`)).toHaveCount(1);
});

test("3D rendering pauses when the hero is scrolled out of view", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(hero)).toHaveAttribute("data-hero-mode", "3d", { timeout: 20_000 });
  await expect(page.locator(`${hero} [data-rendering]`)).toHaveAttribute("data-rendering", "true");
  await page.getByRole("heading", { name: "Your data stays yours" }).scrollIntoViewIfNeeded();
  await expect(page.locator(`${hero} [data-rendering]`)).toHaveAttribute("data-rendering", "false");
});

test("reduced motion: static illustration only, no 3D canvas", async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: "reduce" });
  const page = await context.newPage();
  await page.goto("/");
  await page.waitForTimeout(2500);
  await expect(page.locator(hero)).toHaveAttribute("data-hero-mode", "static");
  await expect(page.locator(`${hero} canvas`)).toHaveCount(0);
  await expect(page.getByRole("img", { name: /Messy spreadsheet cells flow through a processing core/ })).toBeVisible();
  await context.close();
});

test("without WebGL the page still works with the static illustration", async ({ browser }) => {
  const context = await browser.newContext();
  await context.addInitScript(() => {
    HTMLCanvasElement.prototype.getContext = () => null; // simulate a device with no WebGL
  });
  const page = await context.newPage();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/");
  await page.waitForTimeout(2500);
  await expect(page.locator(hero)).toHaveAttribute("data-hero-mode", "static");
  await page.getByRole("link", { name: "Start Analyzing" }).click();
  await expect(page).toHaveURL(/\/upload$/);
  expect(errors).toEqual([]);
  await context.close();
});

test("before/after comparison works with the keyboard", async ({ page }) => {
  await page.goto("/");
  const slider = page.getByRole("slider", { name: /Before and after comparison/ });
  await slider.scrollIntoViewIfNeeded();
  await expect(slider).toHaveValue("55");
  await slider.focus();
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  await expect(slider).toHaveValue("53");
  await expect(slider).toHaveAttribute("aria-valuetext", "53% original, 47% cleaned");
  await page.keyboard.press("End");
  await expect(slider).toHaveValue("100");
});

test("the 3D library is not shipped to workspace pages", async ({ page }) => {
  const scripts: string[] = [];
  page.on("response", async (res) => {
    if (res.url().includes("/_next/static/chunks/") && res.request().resourceType() === "script") {
      const body = await res.text().catch(() => "");
      if (body.includes("WebGLRenderer")) scripts.push(res.url());
    }
  });
  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "Workspace", level: 1 })).toBeVisible();
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
  await page.waitForLoadState("networkidle");
  expect(scripts, "three.js must only load on the landing page").toEqual([]);
});
