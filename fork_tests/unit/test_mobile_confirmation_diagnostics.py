from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_pr3_mobile_dialog_status_and_diagnostics_modules_exist() -> None:
    expected = {
        "static/css/components/dialog.css",
        "static/js/core/diagnostics.js",
        "static/js/core/dialog.js",
        "static/js/core/status.js",
        "templates/components/dialog.html",
    }
    missing = sorted(path for path in expected if not (ROOT / path).is_file())
    assert not missing, f"missing PR3 primitives: {missing}"


def test_active_client_uses_shared_dialog_instead_of_native_dialogs() -> None:
    source = (ROOT / "static/app.js").read_text(encoding="utf-8")
    native_dialog = re.compile(r"(?<![\w.])(?:window\s*\.\s*)?(?:alert|confirm|prompt)\s*\(")
    assert not native_dialog.search(source)
    assert "panelDialog.confirm(options)" in source
    assert "panelDialog.prompt(options)" in source
    for required_text in ("DELETE LOGS", "CLEAR BANS", "CLEANUP", "BREAK", "DISBAND", "UNINSTALL"):
        assert f'requireText: "{required_text}"' in source


def test_diagnostics_redactor_is_bounded_and_uses_text_content() -> None:
    source = (ROOT / "static/js/core/diagnostics.js").read_text(encoding="utf-8")
    assert "const maxDepth = 6" in source
    assert "const maxEntries = 50" in source
    assert "const maxStringLength = 4000" in source
    assert "authorization|cookie|credential|password" in source
    assert "target.textContent = stringify(value)" in source
    assert "innerHTML" not in source


def test_diagnostics_runtime_vectors_and_background_history() -> None:
    script = r"""
const fs = require("fs");
const target = {textContent: ""};
global.window = {};
global.document = {getElementById: () => target};
eval(fs.readFileSync("static/js/core/diagnostics.js", "utf8"));
const diagnostics = window.NO_PANEL_DIAGNOSTICS;
const vectors = [
  "before -----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY----- after",
  "x".repeat(4500) + "-----BEGIN RSA PRIVATE KEY-----\nsecret\n-----END RSA PRIVATE KEY-----",
  "before -----BEGIN EC PRIVATE KEY-----\nsecret without an end marker",
  "-----BEGIN OPENSSH PRIVATE KEY-----\none\n-----END OPENSSH PRIVATE KEY----- middle "
    + "-----BEGIN PRIVATE KEY-----\ntwo\n-----END PRIVATE KEY-----",
  "Authorization: Bearer visible-bearer",
  "/api/action?access_token=visible-token&signature=visible-signature",
];
for (const value of vectors) {
  const safe = diagnostics.redact(value);
  if (/secret|visible-|\none\n|\ntwo\n/.test(safe)) throw new Error(`secret leaked: ${safe}`);
}
if (!diagnostics.redact("z".repeat(4501)).endsWith("… [truncated]")) {
  throw new Error("ordinary long text was not truncated");
}
const nested = diagnostics.redact({nested: {password: "visible-password"}});
if (nested.nested.password !== "[REDACTED]") throw new Error("nested key was not redacted");
for (let index = 0; index < 25; index += 1) {
  diagnostics.record({
    request: {method: "POST", url: `/api/action/${index}?token=visible-token`, body: {password: "visible-password"}},
    response: {status: 200, data: {authorization: "visible-bearer"}},
  });
}
if (diagnostics.records().length !== 20) throw new Error("operator history is not bounded at 20");
const before = target.textContent;
diagnostics.record({
  background: true,
  request: {url: "/api/background-refresh"},
  response: {status: 200, data: {value: "background"}},
});
if (target.textContent !== before || diagnostics.records().length !== 20) {
  throw new Error("background refresh replaced or evicted foreground history");
}
if (target.textContent.includes("visible-")) throw new Error("rendered diagnostics leaked a secret");
"""
    subprocess.run(["node", "-e", script], cwd=ROOT, check=True)


def test_background_api_calls_are_explicitly_marked() -> None:
    source = (ROOT / "static/app.js").read_text(encoding="utf-8")
    assert 'apiFetch("/api/whoami", { background: true })' in source
    assert 'apiFetch("/api/cluster/state", { background: true })' in source
    assert "const { background = false, diagnostics = true, ...fetchOpts } = opts" in source
    assert "if (diagnostics)" in source


def test_mobile_shell_has_dynamic_viewport_safe_areas_and_focus_hooks() -> None:
    layout = (ROOT / "static/css/layout.css").read_text(encoding="utf-8")
    navigation = (ROOT / "static/js/core/navigation.js").read_text(encoding="utf-8")
    assert "100dvh" in layout
    assert "env(safe-area-inset-top)" in layout
    assert "env(safe-area-inset-bottom)" in layout
    assert "font-size: 16px" in layout
    assert "overflow: visible" in layout
    assert "sidebar.focus()" in navigation
    assert 'event.key === "Escape"' in navigation
    assert "legacyToggle?.focus()" in navigation
