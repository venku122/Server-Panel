document.addEventListener("DOMContentLoaded", () => {
  const serverSwitcher = /** @type {HTMLSelectElement|null} */ (document.getElementById("server-switcher"));
  const sidebar = document.getElementById("panel-sidebar");
  const toggle = /** @type {HTMLButtonElement|null} */ (document.querySelector(".sidebar-toggle"));
  const backdrop = /** @type {HTMLButtonElement|null} */ (document.querySelector(".sidebar-backdrop"));
  const closeButtons = document.querySelectorAll("[data-sidebar-close]");

  function closeSidebar({ restoreFocus = true } = {}) {
    document.body.classList.remove("sidebar-open");
    toggle?.setAttribute("aria-expanded", "false");
    backdrop?.setAttribute("hidden", "");
    if (restoreFocus) toggle?.focus();
  }

  function openSidebar() {
    if (!sidebar || !toggle || !backdrop) return;
    document.body.classList.add("sidebar-open");
    toggle.setAttribute("aria-expanded", "true");
    backdrop.removeAttribute("hidden");
    sidebar.focus();
  }

  toggle?.addEventListener("click", () => {
    if (document.body.classList.contains("sidebar-open")) closeSidebar();
    else openSidebar();
  });
  closeButtons.forEach((button) => button.addEventListener("click", () => closeSidebar()));
  sidebar?.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => closeSidebar({ restoreFocus: false })));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("sidebar-open")) closeSidebar();
  });
  window.matchMedia("(min-width: 761px)").addEventListener("change", (event) => {
    if (event.matches) closeSidebar({ restoreFocus: false });
  });

  serverSwitcher?.addEventListener("change", () => {
    if (serverSwitcher.value) window.location.assign(serverSwitcher.value);
  });
});
