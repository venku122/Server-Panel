(() => {
  "use strict";

  const panelWindow = /** @type {any} */ (window);
  const context = /** @type {{serverId?: string}} */ (panelWindow.NO_PANEL_CONTEXT || {});
  const serverId = String(context.serverId || "");
  const results = document.getElementById("workshop-results");
  const empty = document.getElementById("workshop-empty");
  const count = document.getElementById("workshop-count");
  const sourceNote = document.getElementById("workshop-source-note");
  const previewTitle = document.getElementById("workshop-preview-title");
  const previewMeta = document.getElementById("workshop-preview-meta");
  const previewType = document.getElementById("workshop-preview-type");
  const previewDetails = document.getElementById("workshop-preview-details");
  const previewNote = document.getElementById("workshop-preview-note");
  const addButton = /** @type {HTMLButtonElement} */ (document.getElementById("workshop-add"));
  const partialRow = document.getElementById("workshop-partial-row");
  const partialAck = /** @type {HTMLInputElement} */ (document.getElementById("workshop-partial-ack"));
  const conflictPolicy = /** @type {HTMLSelectElement} */ (document.getElementById("workshop-conflict-policy"));
  const queryInput = /** @type {HTMLInputElement} */ (document.getElementById("workshop-query"));
  const refreshButton = /** @type {HTMLButtonElement} */ (document.getElementById("workshop-refresh"));
  let selectedItem = null;
  let activeFilter = "all";

  function status(message, tone = "info") {
    panelWindow.NO_PANEL_STATUS?.show(message, { tone });
  }

  async function readJson(response) {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.success) throw new Error(payload.error || `Request failed (${response.status})`);
    return payload;
  }

  function valueOrDash(value) {
    if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
    return value || "—";
  }

  function metadataRow(label, value) {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = valueOrDash(value);
    row.append(term, description);
    previewDetails.append(row);
  }

  function statusBadge(label, tone = "neutral") {
    const badge = document.createElement("span");
    badge.className = `status-badge status-badge--${tone}`;
    const dot = document.createElement("span");
    dot.className = "status-dot";
    dot.setAttribute("aria-hidden", "true");
    badge.append(dot, label);
    return badge;
  }

  function showPreview(payload, trigger) {
    const item = payload.item || payload;
    selectedItem = item;
    previewTitle.textContent = item.title || `Workshop item ${item.id}`;
    previewMeta.textContent = `${item.author || "Author unavailable"} · ID ${item.id}`;
    previewType.replaceChildren(statusBadge(item.content_type || "Unknown").firstChild, item.content_type || "Unknown");
    previewDetails.replaceChildren();
    metadataRow("Source", item.source === "workshop" ? "Steam Workshop cache" : item.source);
    metadataRow("Installed", item.installed ? "Installed" : "Not installed");
    metadataRow("Available missions", item.mission_names);
    metadataRow("Current rotation", item.playlist_memberships);
    metadataRow("Updated", item.updated_at);
    const children = payload.collection_items || [];
    const missing = payload.missing_child_ids || [];
    if (item.content_type === "collection") {
      const total = children.length + missing.length;
      metadataRow("Collection completeness", total ? `${children.length} of ${total} children available` : "No children listed");
      metadataRow("Available children", children.map((child) => child.title || child.id));
      metadataRow("Missing children", missing);
      partialRow.hidden = missing.length === 0;
      if (partialRow.hidden) partialAck.checked = false;
    } else {
      partialRow.hidden = true;
      partialAck.checked = false;
    }
    metadataRow("Conflicts", "Calculated before confirmation");
    previewNote.replaceChildren();
    const noteTitle = document.createElement("strong");
    noteTitle.textContent = item.metadata_available ? "Local metadata available." : "Metadata incomplete.";
    const noteBody = document.createElement("span");
    noteBody.textContent = payload.message || "This panel only uses files present on the server host.";
    previewNote.append(noteTitle, noteBody);
    addButton.disabled = !item.can_add;
    panelWindow.NO_PANEL_SHEETS?.open("workshop-detail", trigger);
  }

  async function inspectItem(item, trigger) {
    try {
      const response = await fetch(`/api/servers/${encodeURIComponent(serverId)}/workshop/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reference: item.id }),
      });
      const payload = await readJson(response);
      showPreview(payload.resolved ? payload : item, trigger);
    } catch (error) {
      status(error.message || String(error), "error");
    }
  }

  function itemRow(item) {
    const row = document.createElement("button");
    row.className = "workshop-item";
    row.type = "button";
    row.setAttribute("aria-label", `Inspect ${item.title}`);
    const identity = document.createElement("span");
    identity.className = "workshop-item-identity";
    const title = document.createElement("strong");
    title.textContent = item.title;
    const byline = document.createElement("small");
    byline.textContent = `${item.author || "Author unavailable"} · ${item.id}`;
    identity.append(title, byline);
    const type = document.createElement("span");
    type.textContent = item.content_type || "Unknown";
    const installed = document.createElement("span");
    installed.textContent = item.installed ? "Installed" : "—";
    const rotation = document.createElement("span");
    rotation.textContent = valueOrDash(item.playlist_memberships);
    const updated = document.createElement("span");
    updated.textContent = item.updated_at || "Unknown";
    row.append(
      identity,
      type,
      installed,
      rotation,
      updated,
      statusBadge(item.can_add ? "Ready" : "Unavailable", item.can_add ? "success" : "neutral"),
    );
    row.addEventListener("click", () => inspectItem(item, row));
    return row;
  }

  async function loadLibrary() {
    results.setAttribute("aria-busy", "true");
    count.textContent = "Loading local library…";
    try {
      const apiFilter = activeFilter === "collection" ? "all" : activeFilter;
      const response = await fetch(
        `/api/servers/${encodeURIComponent(serverId)}/workshop?q=${encodeURIComponent(queryInput.value)}&filter=${encodeURIComponent(apiFilter)}`,
      );
      const payload = await readJson(response);
      const items = activeFilter === "collection"
        ? payload.items.filter((item) => item.content_type === "collection")
        : payload.items;
      results.replaceChildren(...items.map(itemRow));
      count.textContent = `${items.length} local ${items.length === 1 ? "resource" : "resources"}`;
      empty.hidden = items.length !== 0;
      sourceNote.textContent = payload.source_note;
      if (!payload.capabilities.rotation_mutation) {
        addButton.disabled = true;
        refreshButton.disabled = true;
        document.querySelectorAll("#workshop-resolve-form input, #workshop-resolve-form button").forEach((control) => {
          /** @type {HTMLInputElement | HTMLButtonElement} */ (control).disabled = true;
        });
      }
    } catch (error) {
      results.replaceChildren();
      empty.hidden = false;
      count.textContent = "Library unavailable";
      status(error.message || String(error), "error");
    } finally {
      results.setAttribute("aria-busy", "false");
    }
  }

  document.getElementById("workshop-search-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadLibrary();
  });
  document.getElementById("workshop-search-toggle")?.addEventListener("click", () => queryInput.focus());
  document.querySelectorAll("[data-workshop-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      activeFilter = button.getAttribute("data-workshop-filter") || "all";
      document.querySelectorAll("[data-workshop-filter]").forEach((candidate) => {
        const selected = candidate === button;
        candidate.classList.toggle("active", selected);
        candidate.setAttribute("aria-pressed", String(selected));
      });
      loadLibrary();
    });
  });
  document.getElementById("workshop-resolve-toggle")?.addEventListener("click", () => {
    const form = document.getElementById("workshop-resolve-form");
    form.hidden = !form.hidden;
    if (!form.hidden) document.getElementById("workshop-reference")?.focus();
  });

  document.getElementById("workshop-resolve-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = /** @type {HTMLInputElement} */ (document.getElementById("workshop-reference"));
    try {
      const response = await fetch(`/api/servers/${encodeURIComponent(serverId)}/workshop/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reference: input.value }),
      });
      const payload = await readJson(response);
      if (!payload.resolved) {
        selectedItem = null;
        status(payload.message, "warning");
        return;
      }
      showPreview(payload, event.submitter);
    } catch (error) {
      status(error.message || String(error), "error");
    }
  });

  addButton?.addEventListener("click", async () => {
    if (!selectedItem) return;
    const placement = /** @type {HTMLSelectElement} */ (document.getElementById("workshop-placement")).value;
    const requestPayload = {
      item_id: selectedItem.id,
      placement,
      conflict_policy: conflictPolicy.value,
      acknowledge_partial_collection: partialAck.checked,
    };
    addButton.disabled = true;
    try {
      const previewResponse = await fetch(`/api/servers/${encodeURIComponent(serverId)}/workshop/rotation/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestPayload),
      });
      const previewPayload = await readJson(previewResponse);
      const rotationPreview = previewPayload.preview;
      metadataRow("File conflicts", rotationPreview.conflicts.map((conflict) => `${conflict.mission_name}: ${conflict.state}`));
      metadataRow("Proposed rotation", [rotationPreview.proposed_slot1.name, rotationPreview.proposed_slot2.name].filter(Boolean).join(" → "));
      metadataRow("Restart requirement", "Required after apply");
      if (!rotationPreview.can_apply) {
        status(rotationPreview.apply_error, "warning");
        return;
      }
      const confirmed = await panelWindow.NO_PANEL_DIALOG?.confirm({
        title: "Apply Workshop rotation change",
        message: `Copy local files for “${selectedItem.title}”, apply the proposed slot change using the ${conflictPolicy.value} conflict policy, and require a restart?`,
        confirmLabel: "Apply rotation change",
      });
      if (!confirmed) return;
      const response = await fetch(`/api/servers/${encodeURIComponent(serverId)}/workshop/rotation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestPayload),
      });
      const payload = await readJson(response);
      const remaining = payload.remaining.length ? ` ${payload.remaining.length} additional missions did not fit.` : "";
      status(`Added ${payload.added.join(", ")} to the current rotation. Restart required.${remaining}`, "success");
      panelWindow.NO_PANEL_SHEETS?.close();
      await loadLibrary();
    } catch (error) {
      status(error.message || String(error), "error");
    } finally {
      addButton.disabled = false;
    }
  });

  refreshButton?.addEventListener("click", async () => {
    try {
      const response = await fetch("/api/sync-workshop-missions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ server_id: serverId }),
      });
      const payload = await readJson(response);
      status(`Workshop refresh queued as job ${payload.job.id}.`, "success");
    } catch (error) {
      status(error.message || String(error), "error");
    }
  });

  loadLibrary();
})();
