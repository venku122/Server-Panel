(() => {
  "use strict";

  async function requestJson(url, options = {}) {
    const response = await fetch(url, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
    const payload = await response.json();
    if (!response.ok || !payload.success) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
  }

  function versionEntries() {
    return /** @type {HTMLElement[]} */ ([...document.querySelectorAll("[data-version-id]")]);
  }

  async function loadDiff(versionId, sheet) {
    const output = sheet.querySelector("[data-version-diff-output]");
    const serverId = String(/** @type {any} */ (window).NO_PANEL_CONTEXT?.serverId || "");
    if (output) output.textContent = "Loading normalized diff…";
    try {
      const payload = await requestJson(`/api/config-versions/${encodeURIComponent(versionId)}/diff?server_id=${encodeURIComponent(serverId)}`);
      if (output) output.textContent = payload.diff.changes.length ? JSON.stringify(payload.diff.changes, null, 2) : "No value changes from the previous version.";
    } catch (error) {
      if (output) output.textContent = `Diff unavailable: ${String(error)}`;
    }
  }

  versionEntries().forEach((row) => {
    const versionId = String(row.dataset.versionId || "");
    const sheet = document.getElementById(`config-version-detail-${versionId}`);
    if (!sheet) return;
    row.addEventListener("click", () => loadDiff(versionId, sheet));
    sheet.querySelector("[data-version-diff]")?.addEventListener("click", () => loadDiff(versionId, sheet));
    sheet.querySelector("[data-version-restore]")?.addEventListener("click", async () => {
      const confirmed = await /** @type {any} */ (window).NO_PANEL_DIALOG?.confirm({
        title: "Restore configuration version?",
        message: "This writes the selected historical content as a new current version. Existing history is preserved, but the server may require a restart.",
        confirmLabel: "Restore as new version",
        tone: "danger",
      });
      if (!confirmed) return;
      const serverId = String(/** @type {any} */ (window).NO_PANEL_CONTEXT?.serverId || "");
      try {
        await requestJson(`/api/config-versions/${encodeURIComponent(versionId)}/restore`, { method: "POST", body: JSON.stringify({ server_id: serverId }) });
        window.location.reload();
      } catch (error) {
        /** @type {any} */ (window).NO_PANEL_STATUS?.show(String(error), { level: "error", focus: true });
      }
    });
  });
})();
