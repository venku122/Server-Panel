const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const baseURL = (process.env.PANEL_BASE_URL || "http://127.0.0.1:5000").replace(/\/$/, "");
const username = process.env.PANEL_REVIEW_USERNAME;
const password = process.env.PANEL_REVIEW_PASSWORD;
const outputDir = path.resolve(process.env.PANEL_CAPTURE_DIR || "artifacts/pr1/recheck");

if (!username || !password) {
  throw new Error("PANEL_REVIEW_USERNAME and PANEL_REVIEW_PASSWORD are required");
}

async function signIn(page) {
  await page.goto(`${baseURL}/login`, { waitUntil: "networkidle" });
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(password);
  await Promise.all([
    page.waitForLoadState("networkidle"),
    page.locator('button[type="submit"]').click(),
  ]);
}

async function measure(page) {
  return page.evaluate(() => ({
    url: location.href,
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
    documentWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    scope: window.NO_PANEL_CONTEXT?.scope || null,
    serverId: window.NO_PANEL_CONTEXT?.serverId || null,
    activePage: window.NO_PANEL_CONTEXT?.activePage || null,
    globalPillPresent: Boolean(document.getElementById("pill")),
  }));
}

(async () => {
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const results = { browser: await browser.version(), captures: [], consoleErrors: [], pageErrors: [] };

  for (const viewport of [
    { name: "desktop", width: 1200, height: 800, isMobile: false },
    { name: "iphone", width: 390, height: 844, isMobile: true },
  ]) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      isMobile: viewport.isMobile,
      hasTouch: viewport.isMobile,
    });
    const page = await context.newPage();
    page.on("console", (message) => {
      if (message.type() === "error") results.consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => results.pageErrors.push(error.message));

    await signIn(page);
    await page.waitForURL(`${baseURL}/servers`);
    await page.waitForSelector(".server-card");
    await page.locator(".global-main").scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(outputDir, `servers-${viewport.name}.png`), fullPage: false });
    const listCapture = await measure(page);
    assert.equal(listCapture.horizontalOverflow, false);
    assert.equal(listCapture.globalPillPresent, false);
    results.captures.push({ name: `servers-${viewport.name}`, ...listCapture });

    await Promise.all([
      page.waitForURL(/\/servers\/[^/]+$/),
      page.locator(".server-card").first().click(),
    ]);
    await page.waitForSelector("#page-dashboard.show");
    await page.locator("main.main").scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(outputDir, `server-overview-${viewport.name}.png`), fullPage: false });
    const serverCapture = await measure(page);
    assert.equal(serverCapture.horizontalOverflow, false);
    assert.equal(serverCapture.scope, "server");
    assert.ok(serverCapture.serverId);
    results.captures.push({ name: `server-overview-${viewport.name}`, ...serverCapture });
    await context.close();
  }

  assert.deepEqual(results.consoleErrors, []);
  assert.deepEqual(results.pageErrors, []);
  fs.writeFileSync(path.join(outputDir, "validation-results.json"), `${JSON.stringify(results, null, 2)}\n`);
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
