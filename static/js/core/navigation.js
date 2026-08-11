document.addEventListener("DOMContentLoaded", () => {
  const serverSwitcher = document.getElementById("server-switcher");
  const sidebar = document.getElementById("panel-sidebar");
  const legacyToggle = document.querySelector(".sidebar-toggle");
  const legacyBackdrop = document.querySelector(".sidebar-backdrop");
  let activeDrawer = null;
  let drawerTrigger = null;
  let activeSheet = null;
  let sheetTrigger = null;

  const focusableIn = (element) => [...element.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])')];

  const closeSidebar = ({ restoreFocus = true } = {}) => {
    document.body.classList.remove("sidebar-open");
    legacyToggle?.setAttribute("aria-expanded", "false");
    legacyBackdrop?.setAttribute("hidden", "");
    if (restoreFocus) legacyToggle?.focus();
  };

  const closeDrawer = ({ restoreFocus = true, fromHistory = false } = {}) => {
    if (!activeDrawer) return;
    activeDrawer.hidden = true;
    drawerTrigger?.setAttribute("aria-expanded", "false");
    document.body.classList.remove("drawer-open");
    document.querySelector("[data-overlay-backdrop]")?.setAttribute("hidden", "");
    const trigger = drawerTrigger;
    activeDrawer = null;
    drawerTrigger = null;
    if (restoreFocus) trigger?.focus();
    if (!fromHistory && window.history.state?.panelDrawer) window.history.back();
  };

  const openDrawer = (id, trigger) => {
    const drawer = document.getElementById(id);
    if (!drawer) return;
    if (activeDrawer) closeDrawer({ restoreFocus: false, fromHistory: true });
    activeDrawer = drawer;
    drawerTrigger = trigger;
    drawer.hidden = false;
    trigger?.setAttribute("aria-expanded", "true");
    document.body.classList.add("drawer-open");
    document.querySelector("[data-overlay-backdrop]")?.removeAttribute("hidden");
    window.history.pushState({ panelDrawer: id }, "");
    (focusableIn(drawer)[0] || drawer).focus();
  };

  document.querySelectorAll("[data-open-drawer]").forEach((trigger) => {
    trigger.addEventListener("click", () => openDrawer(trigger.dataset.openDrawer, trigger));
  });
  document.querySelectorAll("[data-close-drawer]").forEach((button) => button.addEventListener("click", () => closeDrawer()));
  document.querySelector("[data-overlay-backdrop]")?.addEventListener("click", () => closeDrawer());
  document.querySelectorAll(".mobile-drawer").forEach((drawer) => {
    drawer.addEventListener("keydown", (event) => {
      if (event.key !== "Tab") return;
      const items = focusableIn(drawer);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
  });
  window.addEventListener("popstate", () => closeDrawer({ restoreFocus: true, fromHistory: true }));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && activeDrawer) { event.preventDefault(); closeDrawer(); }
    else if (event.key === "Escape" && document.body.classList.contains("sidebar-open")) closeSidebar();
  });

  // Keep the previous off-canvas sidebar behavior available to desktop-sized
  // assistive flows, while mobile primary navigation now lives at the bottom.
  legacyToggle?.addEventListener("click", () => {
    if (!sidebar || !legacyBackdrop) return;
    document.body.classList.toggle("sidebar-open");
    const open = document.body.classList.contains("sidebar-open");
    legacyToggle.setAttribute("aria-expanded", String(open));
    legacyBackdrop.toggleAttribute("hidden", !open);
    if (open) sidebar.focus();
  });
  document.querySelectorAll("[data-sidebar-close]").forEach((button) => button.addEventListener("click", () => closeSidebar()));
  serverSwitcher?.addEventListener("change", () => { if (serverSwitcher.value) window.location.assign(serverSwitcher.value); });

  const closeSheet = ({ restoreFocus = true } = {}) => {
    if (!activeSheet) return;
    activeSheet.hidden = true;
    document.body.classList.remove("sheet-open");
    if (!activeDrawer && document.getElementById("find-palette")?.hidden) document.querySelector("[data-overlay-backdrop]")?.setAttribute("hidden", "");
    const trigger = sheetTrigger;
    activeSheet = null;
    sheetTrigger = null;
    if (restoreFocus) trigger?.focus();
  };

  const openSheet = (trigger) => {
    const sheet = document.getElementById(trigger.dataset.openSheet);
    if (!sheet) return;
    if (activeSheet) closeSheet({ restoreFocus: false });
    // The backdrop is a body-level sibling. Promote the active sheet to that
    // same overlay layer so ancestor stacking contexts cannot place it behind
    // the backdrop or block its controls.
    if (sheet.parentElement !== document.body) document.body.append(sheet);
    activeSheet = sheet;
    sheetTrigger = trigger;
    sheet.hidden = false;
    document.body.classList.add("sheet-open");
    document.querySelector("[data-overlay-backdrop]")?.removeAttribute("hidden");
    (focusableIn(sheet)[0] || sheet).focus();
  };

  window.NO_PANEL_SHEETS = {
    open(id, trigger = null) {
      const source = trigger || document.querySelector(`[data-open-sheet="${CSS.escape(id)}"]`);
      if (!source) return;
      source.dataset.openSheet = id;
      openSheet(source);
    },
    close: closeSheet,
  };

  document.querySelectorAll("[data-open-sheet]").forEach((trigger) => {
    trigger.addEventListener("click", () => openSheet(trigger));
    trigger.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      openSheet(trigger);
    });
  });
  document.querySelectorAll("[data-close-sheet]").forEach((button) => button.addEventListener("click", () => closeSheet()));
  document.querySelector("[data-overlay-backdrop]")?.addEventListener("click", () => closeSheet());
  document.querySelectorAll(".detail-sheet").forEach((sheet) => {
    sheet.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { event.preventDefault(); closeSheet(); return; }
      if (event.key !== "Tab") return;
      const items = focusableIn(sheet);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
  });
});
