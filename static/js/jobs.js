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

  const jobCards = () => /** @type {HTMLElement[]} */ ([...document.querySelectorAll("[data-job-id]")]);

  async function jobRequest(url, options = {}) {
    const background = options.background === true;
    const requestOptions = {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
      background,
      diagnostics: !background,
    };
    const panelApiFetch = /** @type {any} */ (window).apiFetch;
    let ok;
    let payload;
    let status;
    if (typeof panelApiFetch === "function") {
      const result = await panelApiFetch(url, requestOptions);
      ok = result.ok;
      payload = result.data || {};
      status = result.status;
    } else {
      const { background: _background, diagnostics: _diagnostics, ...fetchOptions } = requestOptions;
      const result = await fetch(url, fetchOptions);
      ok = result.ok;
      payload = await result.json();
      status = result.status;
    }
    if (!ok || !payload.success) throw new JobRequestError(payload.error || `HTTP ${status}`, payload, status);
    return payload;
  }

  function drawEvents(container, events = []) {
    container.replaceChildren();
    if (!events.length) {
      const empty = document.createElement("li");
      empty.textContent = "No durable events recorded.";
      container.append(empty);
      return;
    }
    events.forEach((event) => {
      const item = document.createElement("li");
      const sequence = document.createElement("span");
      const message = document.createElement("span");
      const timestamp = document.createElement("small");
      sequence.textContent = String(event.sequence);
      message.textContent = event.message;
      timestamp.textContent = new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      item.append(sequence, message, timestamp);
      container.append(item);
    });
  }

  function render(card, job) {
    const sheet = document.getElementById(`job-detail-${job.id}`);
    const statusNodes = [...card.querySelectorAll("[data-job-status]")];
    if (sheet) statusNodes.push(...sheet.querySelectorAll("[data-job-status]"));
    statusNodes.forEach((node) => {
      node.textContent = job.status.replaceAll("_", " ");
      node.dataset.jobStatus = job.status;
      node.className = `job-state job-state--${job.status}`;
      const dot = document.createElement("span");
      dot.className = "status-dot";
      dot.setAttribute("aria-hidden", "true");
      node.prepend(dot);
    });
    const rowProgress = card.querySelector("progress");
    if (rowProgress) {
      rowProgress.max = job.progress_total || 1;
      rowProgress.value = job.progress_current || 0;
    }
    if (sheet) {
      const percentage = job.progress_total ? Math.round((job.progress_current / job.progress_total) * 100) : 0;
      const sheetProgress = sheet.querySelector("progress");
      if (sheetProgress) sheetProgress.value = percentage;
      const percentageLabel = sheet.querySelector(".progress-block > div span:last-child");
      if (percentageLabel) percentageLabel.textContent = `${percentage}%`;
      const step = sheet.querySelector("[data-job-step]");
      if (step) step.textContent = job.events?.at(-1)?.message || job.error_summary || job.status;
      const events = sheet.querySelector("[data-job-events]");
      if (events) drawEvents(events, job.events);
      const result = sheet.querySelector("[data-job-result]");
      if (result) result.textContent = job.result == null ? "Not available." : JSON.stringify(job.result, null, 2);
    }
    if (terminal.has(job.status)) card.querySelector("[data-job-cancel]")?.remove();
    if (job.status === "cancel_requested") {
      const cancel = card.querySelector("[data-job-cancel]");
      if (cancel) { cancel.disabled = true; cancel.textContent = "Cancellation pending"; }
    }
  }

  async function refresh(card) {
    const payload = await jobRequest(`/api/jobs/${encodeURIComponent(card.dataset.jobId)}`, { background: true });
    render(card, payload.job);
    return payload.job;
  }

  function updateDurations() {
    document.querySelectorAll("[data-job-duration]").forEach((nodeElement) => {
      const node = /** @type {HTMLElement} */ (nodeElement);
      const started = new Date(node.dataset.started).getTime();
      const finished = node.dataset.finished ? new Date(node.dataset.finished).getTime() : Date.now();
      if (!Number.isFinite(started) || !Number.isFinite(finished)) return;
      const seconds = Math.max(0, Math.round((finished - started) / 1000));
      node.textContent = seconds < 60 ? `${seconds}s` : seconds < 3600 ? `${Math.floor(seconds / 60)}m ${seconds % 60}s` : `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
    });
  }

  jobCards().forEach((card) => {
    card.querySelectorAll("[data-open-sheet]").forEach((trigger) => trigger.addEventListener("click", () => refresh(card).catch(() => {})));
    card.querySelector("[data-job-cancel]")?.addEventListener("click", async (event) => {
      event.stopPropagation();
      await jobRequest(`/api/jobs/${encodeURIComponent(card.dataset.jobId)}/cancel`, { method: "POST", body: "{}" });
      await refresh(card);
    });
    card.querySelector("[data-job-retry]")?.addEventListener("click", async (event) => {
      event.stopPropagation();
      const retryButton = /** @type {HTMLElement | null} */ (card.querySelector("[data-job-retry]"));
      let body = {};
      if (retryButton.dataset.forceRequired === "true") {
        const expected = `FORCE RETRY ${card.dataset.jobId}`;
        const acknowledgement = await /** @type {any} */ (window).NO_PANEL_DIALOG?.prompt({ title: "Force a non-replay-safe job?", message: "Side effects may already have occurred. Review the event sequence before continuing.", label: `Type ${expected} to continue`, requireText: expected, tone: "danger", confirmLabel: "Continue" });
        if (acknowledgement == null) return;
        const reason = await /** @type {any} */ (window).NO_PANEL_DIALOG?.prompt({ title: "Record a reason", message: "The actor, reason, source job, and checkpoint will be stored.", label: "Reason", minLength: 3, tone: "danger", confirmLabel: "Force retry" });
        if (reason == null) return;
        body = { force: true, acknowledgement, reason };
      }
      const payload = await jobRequest(`/api/jobs/${encodeURIComponent(card.dataset.jobId)}/retry`, { method: "POST", body: JSON.stringify(body) });
      window.location.assign(`${window.location.pathname}?q=${encodeURIComponent(payload.job.id)}`);
    });
  });

  async function poll() {
    updateDurations();
    await Promise.all(jobCards().map(async (card) => {
      const state = /** @type {HTMLElement | null} */ (card.querySelector("[data-job-status]"))?.dataset.jobStatus;
      if (!terminal.has(state)) await refresh(card).catch(() => {});
    }));
  }
  updateDurations();
  setInterval(poll, 2000);
})();
