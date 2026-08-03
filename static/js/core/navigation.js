document.addEventListener("DOMContentLoaded", () => {
  const serverSwitcher = /** @type {HTMLSelectElement|null} */ (document.getElementById("server-switcher"));
  if (!serverSwitcher) return;

  serverSwitcher.addEventListener("change", () => {
    if (serverSwitcher.value) window.location.assign(serverSwitcher.value);
  });
});
