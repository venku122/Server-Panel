(() => {
  "use strict";

  const appStatus = document.getElementById("app-status");

  function targetStatus(preferred) {
    return preferred || document.getElementById("page-status") || appStatus;
  }

  function show(message, options = {}) {
    const target = targetStatus(options.target);
    if (!target) return;
    const text = String(message || "").trim();
    target.textContent = text;
    target.toggleAttribute("hidden", !text);
    target.classList.toggle("notice-warn", options.level === "error");
    target.classList.toggle("notice-good", options.level === "success");
    target.setAttribute("role", options.level === "error" ? "alert" : "status");
    if (appStatus && appStatus !== target) {
      appStatus.textContent = text;
      appStatus.setAttribute("role", options.level === "error" ? "alert" : "status");
    }
    if (options.focus && text) target.focus({ preventScroll: false });
  }

  function clear(target) {
    show("", { target });
  }

  function clearFieldError(field) {
    if (!(field instanceof window.HTMLElement)) return;
    field.removeAttribute("aria-invalid");
    const errorId = field.dataset.fieldErrorId;
    if (errorId) document.getElementById(errorId)?.remove();
    const describedBy = (field.getAttribute("aria-describedby") || "")
      .split(/\s+/)
      .filter((id) => id && id !== errorId);
    if (describedBy.length) field.setAttribute("aria-describedby", describedBy.join(" "));
    else field.removeAttribute("aria-describedby");
    delete field.dataset.fieldErrorId;
  }

  function fieldError(field, message) {
    if (!(field instanceof window.HTMLElement)) {
      show(message, { level: "error", focus: true });
      return;
    }
    clearFieldError(field);
    const id = `${field.id || "field"}-error-${Date.now()}`;
    const error = document.createElement("p");
    error.id = id;
    error.className = "field-error";
    error.textContent = String(message || "Invalid value");
    field.insertAdjacentElement("afterend", error);
    field.dataset.fieldErrorId = id;
    field.setAttribute("aria-invalid", "true");
    const describedBy = new Set((field.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
    describedBy.add(id);
    field.setAttribute("aria-describedby", [...describedBy].join(" "));
    field.focus({ preventScroll: false });
    field.addEventListener("input", () => clearFieldError(field), { once: true });
    show(message, { level: "error" });
  }

  (/** @type {any} */ (window)).NO_PANEL_STATUS = { clear, clearFieldError, fieldError, show };
})();
