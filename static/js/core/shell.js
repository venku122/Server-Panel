document.addEventListener("DOMContentLoaded", () => {
  const root = document.documentElement;
  /** @type {HTMLElement | null} */
  const sidebar = document.querySelector(".sidebar");
  const collapse = document.getElementById("sidebar-collapse");
  /** @type {HTMLElement | null} */
  const resize = document.querySelector("[data-sidebar-resize]");
  /** @type {HTMLElement | null} */
  const find = document.getElementById("find-palette");
  /** @type {HTMLInputElement | null} */
  const findInput = /** @type {HTMLInputElement | null} */ (document.getElementById("find-input"));
  /** @type {HTMLElement | null} */
  const findResults = document.getElementById("find-results");
  /** @type {HTMLElement | null} */
  const backdrop = document.querySelector("[data-overlay-backdrop]");
  /** @type {HTMLElement | null} */
  let restoreFocus = null;
  let results = [];
  let selected = 0;
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);

  const savedWidth = Number(localStorage.getItem("panel.sidebar.width"));
  if (savedWidth >= 208 && savedWidth <= 320) root.style.setProperty("--sidebar-width", `${savedWidth}px`);
  if (localStorage.getItem("panel.sidebar.collapsed") === "true") document.body.classList.add("sidebar-collapsed");

  collapse?.addEventListener("click", () => {
    const collapsed = document.body.classList.toggle("sidebar-collapsed");
    collapse.setAttribute("aria-expanded", String(!collapsed));
    collapse.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
    localStorage.setItem("panel.sidebar.collapsed", String(collapsed));
  });

  resize?.addEventListener("pointerdown", (event) => {
    if (!sidebar || document.body.classList.contains("sidebar-collapsed")) return;
    resize.setPointerCapture(event.pointerId);
    /** @param {PointerEvent} moveEvent */
    const onMove = (moveEvent) => {
      const width = Math.max(208, Math.min(320, moveEvent.clientX));
      root.style.setProperty("--sidebar-width", `${width}px`);
    };
    /** @param {PointerEvent} upEvent */
    const onUp = (upEvent) => {
      resize.releasePointerCapture(upEvent.pointerId);
      resize.removeEventListener("pointermove", onMove);
      resize.removeEventListener("pointerup", onUp);
      localStorage.setItem("panel.sidebar.width", String(Math.round(sidebar.getBoundingClientRect().width)));
    };
    resize.addEventListener("pointermove", onMove);
    resize.addEventListener("pointerup", onUp);
  });

  const closeFind = () => {
    if (!find || find.hidden) return;
    find.hidden = true;
    if (backdrop) backdrop.hidden = true;
    document.body.classList.remove("overlay-open");
    restoreFocus?.focus();
  };

  const drawResults = (query = "") => {
    if (!findResults) return;
    const indexNode = document.getElementById("find-index");
    const index = indexNode ? JSON.parse(indexNode.textContent || "[]") : [];
    const needle = query.trim().toLowerCase();
    results = index.filter((entry) => !needle || `${entry.label} ${entry.description} ${entry.keywords}`.toLowerCase().includes(needle)).slice(0, 12);
    selected = Math.min(selected, Math.max(0, results.length - 1));
    if (!results.length) {
      findResults.innerHTML = '<div class="command-empty">No matching servers or destinations.</div>';
      return;
    }
    let lastGroup = "";
    findResults.innerHTML = results.map((entry, index) => {
      const heading = entry.group !== lastGroup ? `<div class="command-group">${escapeHtml(entry.group)}</div>` : "";
      lastGroup = entry.group;
      return `${heading}<a role="option" aria-selected="${index === selected}" class="command-result${index === selected ? " selected" : ""}" href="${escapeHtml(entry.href)}" data-result-index="${index}"><span><strong>${escapeHtml(entry.label)}</strong><small>${escapeHtml(entry.description)}</small></span><span aria-hidden="true">↵</span></a>`;
    }).join("");
  };

  /** @param {HTMLElement | null} trigger */
  const openFind = (trigger) => {
    if (!find || !findInput) return;
    restoreFocus = trigger || /** @type {HTMLElement | null} */ (document.activeElement);
    find.hidden = false;
    if (backdrop) backdrop.hidden = false;
    document.body.classList.add("overlay-open");
    findInput.value = "";
    drawResults();
    findInput.focus();
  };

  document.querySelectorAll("[data-open-find]").forEach((button) => button.addEventListener("click", () => openFind(/** @type {HTMLElement} */ (button))));
  backdrop?.addEventListener("click", closeFind);
  findInput?.addEventListener("input", () => { selected = 0; drawResults(findInput.value); });
  findInput?.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      selected = Math.max(0, Math.min(results.length - 1, selected + (event.key === "ArrowDown" ? 1 : -1)));
      drawResults(findInput.value);
    } else if (event.key === "Enter" && results[selected]) {
      window.location.assign(results[selected].href);
    }
  });
  find?.addEventListener("keydown", (event) => {
    if (event.key !== "Tab") return;
    const focusable = /** @type {HTMLElement[]} */ ([...find.querySelectorAll("input, a[href], button:not([disabled])")]);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      find?.hidden ? openFind(/** @type {HTMLElement | null} */ (document.activeElement)) : closeFind();
    } else if (event.key === "Escape") {
      if (find && !find.hidden) closeFind();
      else {
        /** @type {HTMLElement | null} */
        const expanded = document.querySelector('[data-menu-button][aria-expanded="true"]');
        document.querySelectorAll(".resource-menu").forEach((node) => { /** @type {HTMLElement} */ (node).hidden = true; });
        document.querySelectorAll("[data-menu-button]").forEach((node) => node.setAttribute("aria-expanded", "false"));
        expanded?.focus();
      }
    }
  });

  document.querySelectorAll("[data-menu-button]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const menu = document.getElementById(button.getAttribute("aria-controls"));
      const expanded = button.getAttribute("aria-expanded") === "true";
      document.querySelectorAll(".resource-menu").forEach((node) => { /** @type {HTMLElement} */ (node).hidden = true; });
      document.querySelectorAll("[data-menu-button]").forEach((node) => node.setAttribute("aria-expanded", "false"));
      if (menu && !expanded) { menu.hidden = false; button.setAttribute("aria-expanded", "true"); /** @type {HTMLElement | null} */ (menu.querySelector("a,button"))?.focus(); }
    });
  });
  document.addEventListener("click", () => {
    document.querySelectorAll(".resource-menu").forEach((node) => { /** @type {HTMLElement} */ (node).hidden = true; });
    document.querySelectorAll("[data-menu-button]").forEach((node) => node.setAttribute("aria-expanded", "false"));
  });

  document.querySelectorAll(".page-tabs").forEach((tablistNode) => {
    const tablist = /** @type {HTMLElement} */ (tablistNode);
    const tabs = /** @type {HTMLElement[]} */ ([...tablist.querySelectorAll("a[href]")]);
    tablist.setAttribute("role", "tablist");
    tabs.forEach((tab) => tab.setAttribute("role", "tab"));
    tablist.addEventListener("keydown", (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const current = Math.max(0, tabs.indexOf(/** @type {HTMLElement} */ (document.activeElement)));
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      tabs[next]?.focus();
    });
  });
});
