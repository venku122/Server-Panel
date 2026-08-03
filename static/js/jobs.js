(() => {
  "use strict";

  const terminal = new Set(["succeeded", "failed", "cancelled", "interrupted"]);

  function jobCards() {
    return [...document.querySelectorAll("[data-job-id]")].map(
      (element) => /** @type {HTMLElement} */ (element),
    );
  }

  async function jobRequest(url, options = {}) {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const payload = await response.json();
    if (!response.ok || !payload.success) throw new Error(payload.error || `HTTP ${response.status}`);
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
    if (terminal.has(job.status)) card.querySelector("[data-job-cancel]")?.remove();
  }

  async function refresh(card) {
    const payload = await jobRequest(`/api/jobs/${encodeURIComponent(card.dataset.jobId)}`);
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
      const payload = await jobRequest(`/api/jobs/${encodeURIComponent(card.dataset.jobId)}/retry`, { method: "POST", body: "{}" });
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
