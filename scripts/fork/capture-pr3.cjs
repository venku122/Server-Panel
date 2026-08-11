const assert = require("assert");
const fs = require("fs");
const path = require("path");

const root = path.resolve(".");
const { chromium } = require(path.join(root, "fork_tools/node_modules/playwright"));
const configPath = path.resolve(process.env.PANEL_CAPTURE_CONFIG || "fork_tools/validation/pr03-browser.json");
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
    documentHeight: document.documentElement.scrollHeight,
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
    await page.addInitScript(() => {
      globalThis.__nativeDialogCalls = [];
      globalThis.alert = (...args) => globalThis.__nativeDialogCalls.push(["alert", ...args]);
      globalThis.confirm = (...args) => {
        globalThis.__nativeDialogCalls.push(["confirm", ...args]);
        return false;
      };
      globalThis.prompt = (...args) => {
        globalThis.__nativeDialogCalls.push(["prompt", ...args]);
        return null;
      };
    });
    const destructiveRequests = [];
    page.on("request", (request) => {
      if (request.method() === "DELETE") destructiveRequests.push(request.url());
    });
    page.on("console", (message) => {
      if (message.type() === "error") results.consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => results.pageErrors.push(error.message));

    await signIn(page);
    await page.goto(`${baseURL}/servers/alpha-operations`, { waitUntil: "networkidle" });
    const overview = await measure(page);
    await page.screenshot({ path: path.join(outputDir, `server-overview-${viewport.name}.png`), fullPage: false });
    results.captures.push({ name: `server-overview-${viewport.name}`, viewport: viewport.name, ...overview });

    if (capturePhase === "after") {
      record(results, `${viewport.name}-overview-no-overflow`, !overview.horizontalOverflow, { route: overview.url });
      const diagnostics = page.locator("details.diagnostics-disclosure");
      record(results, "diagnostics-closed-default", await diagnostics.count() === 1 && !await diagnostics.evaluate((node) => node.open));

      if (viewport.name === "desktop") {
        const diagnosticsResult = await page.evaluate(() => {
          const diagnostics = globalThis.NO_PANEL_DIAGNOSTICS;
          const values = [
            "before -----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY----- after",
            "x".repeat(4500) + "-----BEGIN RSA PRIVATE KEY-----\nsecret\n-----END RSA PRIVATE KEY-----",
            "before -----BEGIN EC PRIVATE KEY-----\nsecret without an end marker",
            "-----BEGIN OPENSSH PRIVATE KEY-----\none\n-----END OPENSSH PRIVATE KEY----- middle "
              + "-----BEGIN PRIVATE KEY-----\ntwo\n-----END PRIVATE KEY-----",
            "Authorization: Bearer visible-bearer",
            "/api/action?access_token=visible-token&signature=visible-signature",
            { nested: { password: "visible-password", token: "visible-token" } },
          ];
          const redacted = diagnostics.stringify(values);
          diagnostics.record({
            request: { method: "POST", url: "/api/operator-action?token=visible-token", body: { password: "visible-password" } },
            response: { status: 200, data: { authorization: "visible-bearer", success: true } },
          });
          const beforeBackground = document.getElementById("response-area").textContent;
          diagnostics.record({
            background: true,
            request: { method: "GET", url: "/api/background-refresh" },
            response: { status: 200, data: { refresh: true } },
          });
          return {
            redacted,
            foregroundHistory: diagnostics.records(),
            backgroundStable: document.getElementById("response-area").textContent === beforeBackground,
          };
        });
        record(
          results,
          "diagnostics-redacts-sensitive-values",
          diagnosticsResult.redacted.includes("[REDACTED]")
            && !diagnosticsResult.redacted.includes("secret")
            && !diagnosticsResult.redacted.includes("visible-")
            && diagnosticsResult.foregroundHistory.length >= 1,
        );
        record(results, "background-refresh-preserves-foreground-diagnostics", diagnosticsResult.backgroundStable);
        record(results, "desktop-drawer-toggle-hidden", !await page.locator(".sidebar-toggle").isVisible());
        await page.locator("#update-server-btn").click();
        await page.locator("#app-dialog").waitFor({ state: "visible" });
        const dialogTitle = await page.locator("#app-dialog-title").textContent();
        const nativeCalls = await page.evaluate(() => globalThis.__nativeDialogCalls.length);
        record(results, "shared-confirmation-dialog", dialogTitle === "Update selected server" && nativeCalls === 0);
        await page.locator("#app-dialog-cancel").click();
      }

      if (viewport.isMobile) {
        const toggle = page.locator(".sidebar-toggle");
        await toggle.click();
        await page.waitForTimeout(260);
        const drawerFocused = await page.locator("#panel-sidebar").evaluate((node) => node === document.activeElement);
        const stickyContext = await page.locator(".mobile-appbar").evaluate((node) => window.getComputedStyle(node).position === "sticky");
        await page.screenshot({ path: path.join(outputDir, `server-drawer-${viewport.name}.png`), fullPage: false });
        results.captures.push({ name: `server-drawer-${viewport.name}`, viewport: viewport.name, ...await measure(page) });
        await page.keyboard.press("Escape");
        const focusRestored = await toggle.evaluate((node) => node === document.activeElement);
        record(results, `${viewport.name}-drawer-focus-escape`, drawerFocused && focusRestored);
        record(results, `${viewport.name}-sticky-server-context`, stickyContext);
      }
    }

    await page.goto(`${baseURL}/servers/alpha-operations/settings`, { waitUntil: "networkidle" });
    const settings = await measure(page);
    await page.screenshot({ path: path.join(outputDir, `server-settings-${viewport.name}.png`), fullPage: false });
    results.captures.push({ name: `server-settings-${viewport.name}`, viewport: viewport.name, ...settings });

    if (capturePhase === "after") {
      record(results, `${viewport.name}-settings-no-overflow`, !settings.horizontalOverflow, { route: settings.url });
      if (viewport.name === "iphone-portrait") {
        const inputFontSize = await page.locator("#startup-fps").evaluate((node) => window.getComputedStyle(node).fontSize);
        record(results, "iphone-no-input-zoom", inputFontSize === "16px", { inputFontSize });

        await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
        await page.waitForTimeout(50);
        const scrollState = await page.evaluate(() => ({
          scrollY: window.scrollY,
          mainOverflow: window.getComputedStyle(document.querySelector("main")).overflowY,
        }));
        record(results, "natural-document-scroll", scrollState.scrollY > 0 && scrollState.mainOverflow === "visible", scrollState);
        await page.evaluate(() => window.scrollTo(0, 0));

        await page.locator("#startup-fps").fill("0");
        await page.locator("#startup-save-btn").click();
        const fieldError = await page.locator("#startup-fps").evaluate((node) => ({
          invalid: node.getAttribute("aria-invalid") === "true",
          focused: node === document.activeElement,
        }));
        record(results, "field-error-focus", fieldError.invalid && fieldError.focused, fieldError);

        await page.locator("#sm-delete-files").check();
        await page.locator("#sm-delete").click();
        await page.locator("#app-dialog").waitFor({ state: "visible" });
        await page.locator("#app-dialog-input").fill("wrong server name");
        await page.locator("#app-dialog-confirm").click();
        const typedGuard = await page.locator("#app-dialog").evaluate((dialog) => dialog.open)
          && await page.locator("#app-dialog-input").getAttribute("aria-invalid") === "true"
          && destructiveRequests.length === 0;
        record(results, "typed-confirmation-guards-destructive-request", typedGuard, { destructiveRequests });
        await page.locator("#app-dialog-cancel").click();
      }
    }
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
