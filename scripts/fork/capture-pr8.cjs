const assert = require("assert");
const fs = require("fs");
const path = require("path");

const root = path.resolve(".");
const { chromium } = require(path.join(root, "fork_tools/node_modules/playwright"));
const configPath = path.resolve(process.env.PANEL_CAPTURE_CONFIG || "fork_tools/validation/pr08-browser.json");
const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
const baseURL = (process.env.PANEL_BASE_URL || "http://127.0.0.1:5000").replace(/\/$/, "");
const username = process.env.PANEL_REVIEW_USERNAME;
const password = process.env.PANEL_REVIEW_PASSWORD;
const capturePhase = process.env.PANEL_CAPTURE_PHASE || "after";
if (!["before", "after"].includes(capturePhase)) throw new Error("PANEL_CAPTURE_PHASE must be before or after");
if (!username || !password) throw new Error("PANEL_REVIEW_USERNAME and PANEL_REVIEW_PASSWORD are required");
const outputDir = path.resolve(root, config.evidenceDir, capturePhase);

async function signIn(page) {
  await page.goto(`${baseURL}/login`, { waitUntil: "networkidle" });
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(password);
  await Promise.all([
    page.waitForLoadState("networkidle"),
    page.locator("button.auth-submit").click(),
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
  }));
}

function record(results, id, passed, details = {}) {
  results.assertions.push({ id, passed, details });
  assert.equal(passed, true, id);
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
    physicalSafari: "Unavailable in this environment; Chromium mobile emulation is recorded, not claimed as physical Safari validation.",
  };

  for (const viewport of config.viewports) {
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

    if (capturePhase === "before") {
      await page.goto(`${baseURL}/servers/alpha-operations`, { waitUntil: "networkidle" });
      record(results, `${viewport.name}-before-workshop-sync-present`, await page.locator("#sync-workshop-btn").count() === 1);
    } else {
      await page.goto(`${baseURL}/servers/alpha-operations/workshop`, { waitUntil: "networkidle" });
      await page.locator("#workshop-count").filter({ hasText: "3 local items" }).waitFor();
      record(results, `${viewport.name}-local-index`, await page.locator(".workshop-item").count() === 3);
      record(
        results,
        `${viewport.name}-metadata-absence`,
        await page.locator(".workshop-item", { hasText: "SilentValley" }).getByText("Metadata absent").count() === 1,
      );
      record(results, `${viewport.name}-named-playlist-boundary`, await page.getByText("Public main supports one current two-slot mission rotation").count() === 1);
      if (viewport.name === "desktop") {
        await page.locator("#workshop-reference").fill("https://steamcommunity.com/sharedfiles/filedetails/?id=333");
        await page.getByRole("button", { name: "Resolve metadata" }).click();
        await page.locator("#workshop-preview-title").filter({ hasText: "Weekend Operations" }).waitFor();
        record(results, "collection-local-expansion", await page.getByText("Falcon Ridge, SilentValley", { exact: true }).count() === 1);
        record(results, "collection-missing-child-visible", await page.getByText("999", { exact: true }).count() === 1);
        await page.locator("#workshop-partial-ack").check();
        await page.locator("#workshop-conflict-policy").selectOption("replace");
        await page.locator("#workshop-add").click();
        await page.locator("#app-dialog").waitFor({ state: "visible" });
        record(results, "metadata-before-confirmation", await page.locator("#workshop-preview-title").textContent() === "Weekend Operations");
        record(results, "conflict-preview", await page.getByText("FalconRidge: different, SilentValley: new", { exact: true }).count() === 1);
        record(results, "proposed-rotation-preview", await page.getByText("FalconRidge → SilentValley", { exact: true }).count() === 1);
        record(results, "restart-preview", await page.getByText("Required after apply", { exact: true }).count() === 1);
        record(results, "shared-confirmation", await page.locator("#app-dialog-title").textContent() === "Apply Workshop rotation change");
        await page.locator("#app-dialog-cancel").click();
      }
      if (viewport.isMobile) {
        const inputSize = await page.locator("#workshop-query").evaluate((node) => window.getComputedStyle(node).fontSize);
        record(results, "iphone-no-input-zoom", inputSize === "16px", { inputSize });
      }
    }

    const dimensions = await measure(page);
    record(results, `${viewport.name}-${capturePhase}-no-overflow`, !dimensions.horizontalOverflow, dimensions);
    const name = `workshop-${capturePhase}-${viewport.name}.png`;
    await page.screenshot({ path: path.join(outputDir, name), fullPage: false });
    results.captures.push({ name, viewport: viewport.name, ...dimensions });
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
