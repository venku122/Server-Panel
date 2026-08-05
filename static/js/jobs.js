(() => {
  "use strict";

  const terminal = new Set(["succeeded", "failed", "cancelled", "interrupted"]);

  class JobRequestError extends Error {
    constructor(message, payload, status) {
      super(message);
      this.payload = payload;
      this.status = status;
    }
  }

  function jobCards() {
    return [...document.querySelectorAll("[data-job-id]")].map(
      (element) => /** @type {HTMLElement} */ (element),
    );
  }

  async function jobRequest(url, options = {}) {
    const background = options.background === true;
    const requestOptions = {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
      background,
      diagnostics: !background,
    };
    let response;
    let payload;
    let status;
    const panelApiFetch = (/** @type {any} */ (window)).apiFetch;
    if (typeof panelApiFetch === "function") {
      const result = await panelApiFetch(url, requestOptions);
      response = result.ok;
      payload = result.data || {};
      status = result.status;
    } else {
      const { background: _background, diagnostics: _diagnostics, ...fetchOptions } = requestOptions;
      const result = await fetch(url, fetchOptions);
      response = result.ok;
      payload = await result.json();
      status = result.status;
    }
    if (!response || !payload.success) {
      throw new JobRequestError(payload.error || `HTTP ${status}`, payload, status);
    }
    return payload;
  }

  function render(card, job) {
    const status = card.querySelector("[data-job-status]");
    if (status) {
      status.textContent = job.status;
      status.dataset.jobStatus = job.status;
    }
    const progress = card.querySelector("progress");
    if (progress) {
      progress.max = job.progress_total || 1;
      progress.value = job.progress_current || 0;
    }
    const progressText = card.querySelector(".job-progress span");
    if (progressText) progressText.textContent = `${job.progress_current} / ${job.progress_total}`;
    const lastEvent = job.events?.at(-1);
    const step = card.querySelector("[data-job-step]");
    if (step) step.textContent = lastEvent?.message || job.error_summary || job.status;
    const events = card.querySelector("[data-job-events]");
    if (events) {
      events.textContent = (job.events || []).map((event) =>
        `${event.sequence}. [${event.level}] ${event.message}`
      ).join("\n") || "No events recorded.";
    }
    const result = card.querySelector("[data-job-result]");
    if (result) result.textContent = job.result == null ? "Not available." : JSON.stringify(job.result, null, 2);
    const cancelButton = /** @type {HTMLButtonElement | null} */ (card.querySelector("[data-job-cancel]"));
    if (terminal.has(job.status)) cancelButton?.remove();
    if (job.status === "cancel_requested" && cancelButton) {
      cancelButton.disabled = true;
      cancelButton.textContent = "Cancellation pending at safe checkpoint";
    }
  }

  async function refresh(card) {
    const payload = await jobRequest(`/api/jobs/${encodeURIComponent(card.dataset.jobId)}`, { background: true });
    render(card, payload.job);
    return payload.job;
  }

  jobCards().forEach((card) => {
    card.querySelector("details")?.addEventListener("toggle", () => {
      if (card.querySelector("details")?.open) refresh(card).catch(() => {});
    });
    card.querySelector("[data-job-cancel]")?.addEventListener("click", async () => {
      await jobRequest(`/api/jobs/${encodeURIComponent(card.dataset.jobId)}/cancel`, { method: "POST", body: "{}" });
      await refresh(card);
    });
    card.querySelector("[data-job-retry]")?.addEventListener("click", async () => {
      const retryButton = /** @type {HTMLElement} */ (card.querySelector("[data-job-retry]"));
      let body = {};
      if (retryButton.dataset.forceRequired === "true") {
        const expected = `FORCE RETRY ${card.dataset.jobId}`;
        const acknowledgement = await (/** @type {any} */ (window)).NO_PANEL_DIALOG?.prompt({
          title: "Force a non-replay-safe job?",
          message: `Last completed step: ${card.querySelector("[data-job-step]")?.textContent || "unknown"}. Side effects may already have occurred.`,
          label: `Type ${expected} to continue`,
          requireText: expected,
          tone: "danger",
          confirmLabel: "Continue",
        });
        if (acknowledgement == null) return;
        const reason = await (/** @type {any} */ (window)).NO_PANEL_DIALOG?.prompt({
          title: "Record a reason",
          message: "The actor, reason, source job, and last completed step will be stored with the forced retry.",
          label: "Reason",
          minLength: 3,
          tone: "danger",
          confirmLabel: "Force retry",
        });
        if (reason == null) return;
        body = { force: true, acknowledgement, reason };
      }
      const payload = await jobRequest(`/api/jobs/${encodeURIComponent(card.dataset.jobId)}/retry`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      window.location.assign(`/jobs#${payload.job.id}`);
    });
  });

  async function poll() {
    await Promise.all(jobCards().map(async (card) => {
      const status = /** @type {HTMLElement | null} */ (card.querySelector("[data-job-status]"));
      const state = status?.dataset.jobStatus;
      if (!terminal.has(state)) await refresh(card).catch(() => {});
    }));
  }
  setInterval(poll, 2000);
})();
