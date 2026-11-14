// Measures what a first-time visitor downloads and how quickly the main content appears.
// Usage (both servers running, production build):  node scripts/measure-performance.mjs [baseUrl]
// Numbers depend on the machine; compare runs on the same machine only.
import { chromium } from "playwright";

const base = process.argv[2] ?? "http://127.0.0.1:3000";
const browser = await chromium.launch();

async function measure(label, path, prepare) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();
  const target = prepare ? await prepare(page) : path;
  const cdp = await context.newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
  const sizes = { script: 0, stylesheet: 0, image: 0, font: 0, other: 0 };
  const types = new Map();
  cdp.on("Network.responseReceived", (e) => types.set(e.requestId, e.type.toLowerCase()));
  cdp.on("Network.loadingFinished", (e) => {
    const t = types.get(e.requestId);
    sizes[t in sizes ? t : "other"] += e.encodedDataLength; // bytes on the wire (compressed)
  });
  await page.addInitScript(() => {
    window.__lcp = 0;
    window.__cls = 0;
    new PerformanceObserver((l) => l.getEntries().forEach((e) => (window.__lcp = e.startTime))).observe({ type: "largest-contentful-paint", buffered: true });
    new PerformanceObserver((l) => l.getEntries().forEach((e) => !e.hadRecentInput && (window.__cls += e.value))).observe({ type: "layout-shift", buffered: true });
  });
  await page.goto(base + target, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const m = await page.evaluate(() => {
    const nav = performance.getEntriesByType("navigation")[0];
    return { ttfb: nav.responseStart, dcl: nav.domContentLoadedEventEnd, load: nav.loadEventEnd, lcp: window.__lcp, cls: window.__cls };
  });
  const kb = (n) => (n / 1024).toFixed(0).padStart(5);
  console.log(
    `${label.padEnd(18)} JS ${kb(sizes.script)} kB  CSS ${kb(sizes.stylesheet)} kB  images ${kb(sizes.image)} kB  fonts ${kb(sizes.font)} kB | ` +
      `TTFB ${m.ttfb.toFixed(0)} ms  LCP ${m.lcp.toFixed(0)} ms  load ${m.load.toFixed(0)} ms  CLS ${m.cls.toFixed(3)}`,
  );
  await context.close();
}

async function openSample(page) {
  await page.goto(`${base}/upload`);
  await page.getByTestId("samples").getByRole("button", { name: /Sales orders/ }).click();
  await page.getByTestId("raw-preview").waitFor();
  await page.getByRole("button", { name: "Start analysis" }).click();
  await page.waitForURL(/\/health$/);
  return new URL(page.url()).pathname.replace(/\/health$/, "");
}

console.log("Transfer sizes are compressed bytes on the wire, cache disabled.\n");
await measure("Landing", "/");
await measure("Upload Studio", "/upload");
for (const screen of ["health", "clean", "dashboard", "analyst", "export"]) {
  await measure(screen, null, async (page) => `${await openSample(page)}/${screen}`);
}
await browser.close();
