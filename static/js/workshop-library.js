(() => {
  "use strict";

  const panelWindow = /** @type {any} */ (window);
  const context = /** @type {{serverId?: string}} */ (panelWindow.NO_PANEL_CONTEXT || {});
  const serverId = String(context.serverId || "");
  const results = document.getElementById("workshop-results");
  const empty = document.getElementById("workshop-empty");
  const count = document.getElementById("workshop-count");
  const sourceNote = document.getElementById("workshop-source-note");
  const preview = document.getElementById("workshop-preview");
  const previewTitle = document.getElementById("workshop-preview-title");
  const previewMeta = document.getElementById("workshop-preview-meta");
  const previewType = document.getElementById("workshop-preview-type");
  const previewDetails = document.getElementById("workshop-preview-details");
  const previewNote = document.getElementById("workshop-preview-note");
  const addButton = /** @type {HTMLButtonElement} */ (document.getElementById("workshop-add"));
  let selectedItem = null;

  function status(message, tone = "info") {
    panelWindow.NO_PANEL_STATUS?.show(message, { tone });
  }

  async function readJson(response) {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.success) throw new Error(payload.error || `Request failed (${response.status})`);
    return payload;
  }

  function metadataRow(label, value) {
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = value || "Unavailable locally";
    previewDetails.append(term, description);
  }

  function showPreview(payload) {
    const item = payload.item || payload;
    selectedItem = item;
    preview.hidden = false;
    previewTitle.textContent = item.title || `Workshop item ${item.id}`;
    previewMeta.textContent = `${item.author || "Author unavailable"} • ID ${item.id}`;
    previewType.textContent = item.content_type || "unknown";
    previewDetails.replaceChildren();
    metadataRow("Metadata", item.metadata_available ? "Available from local files" : "Not present in local files");
    metadataRow("Missions", (item.mission_names || []).join(", "));
    metadataRow("Current rotation", (item.playlist_memberships || []).join(", "));
    metadataRow("Updated", item.updated_at || "Unavailable locally");
    const children = payload.collection_items || [];
    if (item.content_type === "collection") {
      metadataRow("Cached children", children.map((child) => child.title || child.id).join(", "));
      metadataRow("Missing child IDs", (payload.missing_child_ids || []).join(", "));
    }
    previewNote.textContent = payload.message || (
      item.metadata_available
        ? "Metadata was resolved from local files. Review it before adding to the current rotation."
        : "Metadata is absent locally; the panel will not guess title or author details."
    );
    addButton.disabled = !item.can_add;
    preview.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function itemCard(item) {
    const article = document.createElement("article");
    article.className = "workshop-item";
    const header = document.createElement("div");
    header.className = "workshop-item-header";
    const title = document.createElement("h2");
    title.className = "workshop-item-title";
    title.textContent = item.title;
    const type = document.createElement("span");
    type.className = "status-pill";
    type.textContent = item.content_type;
    header.append(title, type);
    const copy = document.createElement("p");
    copy.className = "workshop-item-copy";
    copy.textContent = `${item.author || "Author unavailable"} • ID ${item.id}`;
    const footer = document.createElement("div");
    footer.className = "workshop-item-footer";
    const availability = document.createElement("span");
    availability.className = "small muted";
    availability.textContent = item.metadata_available ? "Local metadata" : "Metadata absent";
    const inspect = document.createElement("button");
    inspect.className = "btn ghost";
    inspect.type = "button";
    inspect.textContent = "Inspect";
    inspect.addEventListener("click", () => showPreview(item));
    footer.append(availability, inspect);
    article.append(header, copy, footer);
    return article;
  }

  async function loadLibrary() {
    const query = /** @type {HTMLInputElement} */ (document.getElementById("workshop-query")).value;
    const filter = /** @type {HTMLSelectElement} */ (document.getElementById("workshop-filter")).value;
    count.textContent = "Loading local library…";
    try {
      const response = await fetch(
        `/api/servers/${encodeURIComponent(serverId)}/workshop?q=${encodeURIComponent(query)}&filter=${encodeURIComponent(filter)}`,
      );
      const payload = await readJson(response);
      results.replaceChildren(...payload.items.map(itemCard));
      count.textContent = `${payload.items.length} local ${payload.items.length === 1 ? "item" : "items"}`;
      empty.hidden = payload.items.length !== 0;
      sourceNote.textContent = payload.source_note;
    } catch (error) {
      results.replaceChildren();
      empty.hidden = false;
      count.textContent = "Library unavailable";
      status(error.message || String(error), "error");
    }
  }

  document.getElementById("workshop-search-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadLibrary();
  });
  document.getElementById("workshop-filter")?.addEventListener("change", loadLibrary);

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
        preview.hidden = true;
        status(payload.message, "warning");
        return;
      }
      showPreview(payload);
    } catch (error) {
      status(error.message || String(error), "error");
    }
  });

  addButton?.addEventListener("click", async () => {
    if (!selectedItem) return;
    const confirmed = await panelWindow.NO_PANEL_DIALOG?.confirm({
      title: "Add Workshop content",
      message: `Copy local files for “${selectedItem.title}” and update this server's current two-slot rotation?`,
      confirmLabel: "Add to rotation",
    });
    if (!confirmed) return;
    const placement = /** @type {HTMLSelectElement} */ (document.getElementById("workshop-placement")).value;
    addButton.disabled = true;
    try {
      const response = await fetch(`/api/servers/${encodeURIComponent(serverId)}/workshop/rotation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_id: selectedItem.id, placement }),
      });
      const payload = await readJson(response);
      const remaining = payload.remaining.length ? ` ${payload.remaining.length} additional missions did not fit.` : "";
      status(`Added ${payload.added.join(", ")} to the current rotation. Restart required.${remaining}`, "success");
      await loadLibrary();
    } catch (error) {
      status(error.message || String(error), "error");
    } finally {
      addButton.disabled = false;
    }
  });

  document.getElementById("workshop-refresh")?.addEventListener("click", async () => {
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
