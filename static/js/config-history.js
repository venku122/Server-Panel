(() => {
  "use strict";

  async function requestJson(url, options = {}) {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const payload = await response.json();
    if (!response.ok || !payload.success) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
  }

  document.querySelectorAll("[data-version-id]").forEach((element) => {
    const card = /** @type {HTMLElement} */ (element);
    const versionId = String(card.dataset.versionId || "");
    const serverId = String((/** @type {any} */ (window)).NO_PANEL_CONTEXT?.serverId || "");
    card.querySelector("[data-version-diff]")?.addEventListener("click", async () => {
      const output = card.querySelector("[data-version-diff-output]");
      try {
        const payload = await requestJson(`/api/config-versions/${encodeURIComponent(versionId)}/diff?server_id=${encodeURIComponent(serverId)}`);
        if (output) output.textContent = JSON.stringify(payload.diff, null, 2);
        const details = card.querySelector("details");
        if (details) details.open = true;
      } catch (error) {
        if (output) output.textContent = String(error);
      }
    });
    card.querySelector("[data-version-restore]")?.addEventListener("click", async () => {
      const dialog = (/** @type {any} */ (window)).NO_PANEL_DIALOG;
      const confirmed = await dialog.confirm({
        title: "Restore configuration version",
        message: "Restore this historical content as a new current version? Existing history is preserved.",
        confirmLabel: "Restore as new version",
        tone: "danger",
      });
      if (!confirmed) return;
      try {
        const payload = await requestJson(`/api/config-versions/${encodeURIComponent(versionId)}/restore`, {
          method: "POST",
          body: JSON.stringify({ server_id: serverId }),
        });
        window.location.reload();
        return payload;
      } catch (error) {
        (/** @type {any} */ (window)).NO_PANEL_STATUS?.show(String(error), { level: "error", focus: true });
      }
    });
  });
})();
