const assert = require("assert");
const fs = require("fs");
const path = require("path");

const root = path.resolve(".");
const { chromium } = require(path.join(root, "fork_tools/node_modules/playwright"));
const configPath = path.resolve(process.env.PANEL_CAPTURE_CONFIG || "fork_tools/validation/pr02-browser.json");
const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
const baseURL = (process.env.PANEL_BASE_URL || "http://127.0.0.1:5000").replace(/\/$/, "");
const username = process.env.PANEL_REVIEW_USERNAME;
const password = process.env.PANEL_REVIEW_PASSWORD;
const capturePhase = process.env.PANEL_CAPTURE_PHASE || "after";
if (!["before", "after"].includes(capturePhase)) {
  throw new Error("PANEL_CAPTURE_PHASE must be before or after");
}
const outputDir = path.resolve(root, config.evidenceDir, capturePhase);

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
  await page.waitForURL(`${baseURL}/servers`);
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
    stylesheets: [...document.querySelectorAll('link[rel="stylesheet"]')].map((link) => link.href),
  }));
}

function record(results, id, passed, details = {}) {
  results.assertions.push({ id, passed, details });
  assert.equal(passed, true, id);
}

async function focusServerCardWithKeyboard(page) {
  const firstCard = page.locator("a.server-card").first();
  await page.locator("body").click({ position: { x: 1, y: 1 } });
  for (let attempt = 0; attempt < 40; attempt += 1) {
    await page.keyboard.press("Tab");
    if (await firstCard.evaluate((element) => element === document.activeElement)) return true;
  }
  return false;
}

(async () => {
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const results = {
    browser: await browser.version(),
    config: path.relative(root, configPath),
    phase: capturePhase,
    assertions: [],
    captures: [],
    consoleErrors: [],
    pageErrors: [],
  };

  for (const viewport of config.viewports) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      isMobile: viewport.isMobile,
      hasTouch: viewport.isMobile,
    });
    const page = await context.newPage();
    page.on("console", (message) => {
      const sourceURL = message.location().url || "";
      const expectedPreStackMiss =
        message.type() === "error" && sourceURL.includes("/api/startup-settings");
      if (message.type() === "error" && !expectedPreStackMiss) {
        results.consoleErrors.push(message.text());
      }
    });
    page.on("pageerror", (error) => results.pageErrors.push(error.message));

    await signIn(page);
    await page.waitForSelector("a.server-card");
    const globalCapture = await measure(page);
    record(results, "global-shell-renders", Boolean(await page.locator("main").count()), { viewport: viewport.name });
    if (capturePhase === "after") {
      record(
        results,
        "component-styles-load",
        globalCapture.stylesheets.some((href) => href.includes("/static/css/")),
        { viewport: viewport.name, stylesheets: globalCapture.stylesheets },
      );
    }
    if (viewport.name === "desktop") {
      record(results, "keyboard-server-card", await focusServerCardWithKeyboard(page));
    }
    record(results, `${viewport.name}-global-no-overflow`, !globalCapture.horizontalOverflow, { route: "/servers" });
    await page.screenshot({ path: path.join(outputDir, `servers-${viewport.name}.png`), fullPage: false });
    results.captures.push({ name: `servers-${viewport.name}`, ...globalCapture });

    await Promise.all([
      page.waitForURL(/\/servers\/[^/]+$/),
      page.locator("a.server-card").first().click(),
    ]);
    const serverCapture = await measure(page);
    record(
      results,
      "server-shell-renders",
      serverCapture.scope === "server" && Boolean(serverCapture.serverId),
      { viewport: viewport.name },
    );
    record(results, `${viewport.name}-server-no-overflow`, !serverCapture.horizontalOverflow, { route: "server" });
    await page.screenshot({ path: path.join(outputDir, `server-overview-${viewport.name}.png`), fullPage: false });
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
