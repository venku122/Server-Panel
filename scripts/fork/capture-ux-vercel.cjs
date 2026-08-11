const assert = require("assert");
const fs = require("fs");
const path = require("path");

const root = path.resolve(".");
const { chromium } = require(path.join(root, "fork_tools/node_modules/playwright"));
const baseURL = (process.env.PANEL_BASE_URL || "http://127.0.0.1:5104").replace(/\/$/, "");
const username = process.env.PANEL_REVIEW_USERNAME || "reviewadmin";
const password = process.env.PANEL_REVIEW_PASSWORD || "fork-review-password";
const phase = process.env.PANEL_CAPTURE_PHASE || "after";
if (!["before", "after"].includes(phase)) throw new Error("PANEL_CAPTURE_PHASE must be before or after");
const outputDir = path.join(root, "artifacts/ux-vercel/screenshots", phase);

const viewports = [
  { name: "desktop-1200x800", width: 1200, height: 800, mobile: false },
  { name: "desktop-1600x1000", width: 1600, height: 1000, mobile: false },
  { name: "mobile-390x844", width: 390, height: 844, mobile: true },
  { name: "mobile-landscape-844x390", width: 844, height: 390, mobile: true },
];

const routes = [
  ["servers", "/servers"],
  ["server-overview", "/servers/alpha-operations"],
  ["operations", "/servers/alpha-operations/operations"],
  ["global-settings", "/settings"],
  ["server-settings", "/servers/alpha-operations/settings"],
  ["activity", "/activity"],
  ["jobs", "/jobs"],
  ["settings-history", "/servers/alpha-operations/settings/history"],
  ["workshop", "/servers/alpha-operations/workshop"],
  ["players", "/servers/alpha-operations/players"],
  ["moderation", "/servers/alpha-operations/players/moderation"],
];

async function signIn(page) {
  await page.goto(`${baseURL}/login`, { waitUntil: "domcontentloaded" });
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(password);
  await Promise.all([
    page.waitForURL(/\/servers$/),
    page.locator("button.auth-submit").click(),
  ]);
}

async function settle(page) {
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(350);
}

async function open(page, route) {
  await page.goto(`${baseURL}${route}`, { waitUntil: "domcontentloaded" });
  await settle(page);
}

async function capture(page, results, viewport, name) {
  const measurement = await page.evaluate(() => ({
    url: location.href,
    width: window.innerWidth,
    height: window.innerHeight,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  }));
  const file = `${name}-${viewport.name}.png`;
  await page.screenshot({ path: path.join(outputDir, file), fullPage: false });
  results.captures.push({ file, ...measurement });
  if (phase === "after") {
    assert.equal(measurement.overflow, false, `${file} has horizontal overflow`);
  }
}

async function captureAfterStates(page, results, viewport) {
  await open(page, "/servers");
  if (!viewport.mobile) {
    await page.locator("#sidebar-collapse").click();
    await capture(page, results, viewport, "servers-collapsed-sidebar");
    await page.locator("#sidebar-collapse").click();
  }
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await page.locator("#find-input").fill("Alpha jobs");
  await capture(page, results, viewport, "find-palette");
  await page.keyboard.press("Escape");

  await open(page, "/activity?outcome=failure&actor=cluster-member");
  await capture(page, results, viewport, "activity-filters");
  await open(page, "/activity");
  const activityRow = page.locator('[data-open-sheet^="activity-detail-"]').first();
  await activityRow.click();
  await capture(page, results, viewport, "activity-detail");
  await page.locator("[data-close-sheet]:visible").click();
  results.assertions.push({ id: `${viewport.name}-sheet-focus-return`, passed: await activityRow.evaluate((node) => node === document.activeElement) });

  await open(page, "/jobs?status=running");
  await capture(page, results, viewport, "jobs-running");
  const jobRow = page.locator('[data-open-sheet^="job-detail-"]').first();
  await jobRow.click();
  await capture(page, results, viewport, "jobs-detail");
  await page.keyboard.press("Escape");
  const menuButton = page.locator("[data-menu-button]").first();
  await menuButton.click();
  await capture(page, results, viewport, "jobs-menu");

  await open(page, "/servers/alpha-operations/settings/history");
  await page.locator('[data-open-sheet^="config-version-detail-"]').first().click();
  await page.waitForTimeout(250);
  await capture(page, results, viewport, "settings-history-diff");
  await page.locator("[data-version-restore]:visible").click();
  await page.locator("#app-dialog").waitFor({ state: "visible" });
  await capture(page, results, viewport, "settings-history-restore-modal");
  await page.locator("#app-dialog-cancel").click();

  await open(page, "/servers/alpha-operations/workshop");
  await page.locator('button[aria-label="Inspect Falcon Ridge"]').click();
  await capture(page, results, viewport, "workshop-item-detail");
  await page.locator("#workshop-conflict-policy").selectOption("replace");
  await page.locator("#workshop-add").click();
  await page.locator("#app-dialog").waitFor({ state: "visible" });
  await capture(page, results, viewport, "workshop-review-modal");
  await page.locator("#app-dialog-cancel").click();

  if (viewport.mobile) {
    await open(page, "/servers/alpha-operations");
    await page.locator('[data-open-drawer="more-drawer"]').click();
    await capture(page, results, viewport, "mobile-more-drawer");
    await page.keyboard.press("Escape");
    await page.locator('[data-open-drawer="server-selector-drawer"]').click();
    await capture(page, results, viewport, "mobile-server-selector");
    await page.keyboard.press("Escape");
    const drawerFocus = await page.locator('[data-open-drawer="server-selector-drawer"]').evaluate((node) => node === document.activeElement);
    results.assertions.push({ id: `${viewport.name}-drawer-focus-return`, passed: drawerFocus });
  }
}

(async () => {
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const results = { phase, browser: await browser.version(), captures: [], assertions: [], consoleErrors: [], pageErrors: [], mutationRequests: [] };
  for (const viewport of viewports) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      isMobile: viewport.mobile,
      hasTouch: viewport.mobile,
    });
    const page = await context.newPage();
    page.on("console", (message) => { if (message.type() === "error") results.consoleErrors.push({ viewport: viewport.name, text: message.text() }); });
    page.on("pageerror", (error) => results.pageErrors.push({ viewport: viewport.name, text: error.message }));
    page.on("request", (request) => {
      if (request.method() !== "GET" && /\/workshop\/rotation$/.test(new URL(request.url()).pathname)) {
        results.mutationRequests.push({ method: request.method(), url: request.url() });
      }
    });
    await signIn(page);
    for (const [name, route] of routes) {
      await open(page, route);
      await capture(page, results, viewport, name);
    }
    if (phase === "after") await captureAfterStates(page, results, viewport);
    await context.close();
  }
  results.assertions.push({ id: "no-workshop-mutation-before-confirmation", passed: results.mutationRequests.length === 0 });
  for (const assertion of results.assertions) assert.equal(assertion.passed, true, assertion.id);
  assert.deepEqual(results.pageErrors, []);
  fs.writeFileSync(path.join(outputDir, "validation-results.json"), `${JSON.stringify(results, null, 2)}\n`);
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
