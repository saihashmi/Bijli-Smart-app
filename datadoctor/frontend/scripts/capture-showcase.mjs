// Captures the landing-page product screenshots from the RUNNING app, using the bundled synthetic sales sample.
// Usage (both servers running):  node scripts/capture-showcase.mjs [baseUrl]
// The images are real screens of this product; nothing in them is drawn by hand.
import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import path from "node:path";

const base = process.argv[2] ?? "http://127.0.0.1:3000";
const out = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "public", "showcase");
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: "dark", reducedMotion: "reduce" });
const shot = async (name) => {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(out, `${name}.jpg`), type: "jpeg", quality: 82 });
  console.log("saved", name);
};

await page.goto(`${base}/upload`);
await page.getByTestId("samples").getByRole("button", { name: /Sales orders/ }).click();
await page.getByTestId("raw-preview").waitFor();
await page.getByRole("button", { name: "Start analysis" }).click();
await page.waitForURL(/\/health$/);
const root = page.url().replace(/\/health$/, "");
await page.getByTestId("health-score").waitFor();
await page.waitForLoadState("networkidle");
await page.waitForTimeout(4500); // let the "ready" toast leave
await shot("health");

await page.goto(`${root}/clean?op=convert_numeric&column=Amount`);
await page.getByTestId("data-grid").waitFor();
await page.getByRole("button", { name: "Preview on full data" }).click();
await page.waitForLoadState("networkidle");
await shot("cleaning");

await page.goto(`${root}/dashboard`);
await page.getByTestId("widget").first().waitFor();
await page.getByLabel("Dashboard theme").selectOption("midnight");
await page.getByTestId("save-state").getByText("Saved").waitFor();
await page.getByTestId("dashboard-canvas").scrollIntoViewIfNeeded();
await page.waitForTimeout(800);
await page.evaluate(() => document.querySelector('[data-testid="dashboard-canvas"]').scrollIntoView({ block: "start" }));
await page.waitForTimeout(400);
await page.screenshot({ path: path.join(out, "dashboard.jpg"), type: "jpeg", quality: 82 });
console.log("saved dashboard");

await page.goto(`${root}/analyst`);
await page.getByLabel("Your question").fill("Which region has the highest total amount?");
await page.getByRole("button", { name: "Ask", exact: true }).click();
await page.getByTestId("answer").waitFor();
await page.waitForTimeout(500);
await shot("analyst");

await page.goto(`${root}/export`);
await page.getByRole("button", { name: "Create Excel workbook" }).click();
await page.getByTestId("export-job").first().waitFor();
await page.getByRole("button", { name: "Create PDF report" }).click();
await page.getByTestId("export-job").nth(1).waitFor();
await page.waitForTimeout(4500); // let the toasts leave
await shot("export");
await browser.close();
