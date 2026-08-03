(() => {
  "use strict";

  const dialog = /** @type {HTMLDialogElement} */ (document.getElementById("app-dialog"));
  const form = /** @type {HTMLFormElement} */ (document.getElementById("app-dialog-form"));
  const title = /** @type {HTMLElement} */ (document.getElementById("app-dialog-title"));
  const message = /** @type {HTMLElement} */ (document.getElementById("app-dialog-message"));
  const inputField = /** @type {HTMLElement} */ (document.getElementById("app-dialog-input-field"));
  const inputLabel = /** @type {HTMLLabelElement} */ (document.getElementById("app-dialog-input-label"));
  const inputHelp = /** @type {HTMLElement} */ (document.getElementById("app-dialog-input-help"));
  const input = /** @type {HTMLInputElement} */ (document.getElementById("app-dialog-input"));
  const confirmButton = /** @type {HTMLButtonElement} */ (document.getElementById("app-dialog-confirm"));
  const cancelButton = /** @type {HTMLButtonElement} */ (document.getElementById("app-dialog-cancel"));
  const closeButton = /** @type {HTMLButtonElement} */ (document.getElementById("app-dialog-close"));
  let pending = null;
  let mode = "confirm";
  let requiredText = "";
  let minimumLength = 0;

  function finish(value) {
    if (!pending) return;
    const resolve = pending;
    pending = null;
    dialog.close();
    resolve(value);
  }

  function configure(options, nextMode) {
    (/** @type {any} */ (window)).NO_PANEL_STATUS?.clearFieldError(input);
    mode = nextMode;
    requiredText = String(options.requireText || "");
    minimumLength = Number(options.minLength || 0);
    title.textContent = options.title || (mode === "prompt" ? "Enter value" : "Confirm action");
    message.textContent = options.message || "";
    inputLabel.textContent = options.label || (requiredText ? `Type ${requiredText} to continue` : "Value");
    inputHelp.textContent = requiredText ? `Enter “${requiredText}” exactly.` : (options.help || "");
    input.value = options.value || "";
    input.type = options.inputType || "text";
    input.autocomplete = options.autocomplete || "off";
    inputField.toggleAttribute("hidden", mode !== "prompt" && !requiredText);
    confirmButton.textContent = options.confirmLabel || (mode === "prompt" ? "Continue" : "Confirm");
    confirmButton.classList.toggle("danger", options.tone === "danger");
  }

  function open(options = {}, nextMode = "confirm") {
    if (!dialog || !form) return Promise.resolve(nextMode === "prompt" ? null : false);
    if (pending) finish(mode === "prompt" ? null : false);
    configure(options, nextMode);
    dialog.showModal();
    requestAnimationFrame(() => {
      if (!inputField.hidden) input.focus();
      else confirmButton.focus();
    });
    return new Promise((resolve) => { pending = resolve; });
  }

  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    const value = input.value;
    if (requiredText && value !== requiredText) {
      (/** @type {any} */ (window)).NO_PANEL_STATUS?.fieldError(input, `Type “${requiredText}” exactly to continue.`);
      return;
    }
    if (mode === "prompt" && value.length < minimumLength) {
      (/** @type {any} */ (window)).NO_PANEL_STATUS?.fieldError(input, `Enter at least ${minimumLength} characters.`);
      return;
    }
    finish(mode === "prompt" ? value : true);
  });
  cancelButton?.addEventListener("click", () => finish(mode === "prompt" ? null : false));
  closeButton?.addEventListener("click", () => finish(mode === "prompt" ? null : false));
  dialog?.addEventListener("cancel", (event) => {
    event.preventDefault();
    finish(mode === "prompt" ? null : false);
  });
  dialog?.addEventListener("click", (event) => {
    if (event.target === dialog) finish(mode === "prompt" ? null : false);
  });

  (/** @type {any} */ (window)).NO_PANEL_DIALOG = {
    confirm: (options) => open(options, "confirm"),
    prompt: (options) => open(options, "prompt"),
  };
})();
