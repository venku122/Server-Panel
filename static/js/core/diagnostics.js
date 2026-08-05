(() => {
  "use strict";

  const sensitiveKey = /(authorization|cookie|credential|password|passwd|private.?key|secret|session|token|webhook|api.?key)/i;
  const privateKeyBegin = /-----BEGIN ([A-Z0-9 ]*PRIVATE KEY)-----/gi;
  const maxDepth = 6;
  const maxEntries = 50;
  const maxHistoryEntries = 20;
  const maxStringLength = 4000;
  const history = [];

  function redactPrivateKeys(value) {
    let cursor = 0;
    let output = "";
    let match = privateKeyBegin.exec(value);

    while (match) {
      output += value.slice(cursor, match.index);
      output += "[REDACTED PRIVATE KEY]";

      const endMarker = `-----END ${match[1].toUpperCase()}-----`;
      const endIndex = value.toUpperCase().indexOf(endMarker, privateKeyBegin.lastIndex);
      if (endIndex < 0) {
        cursor = value.length;
        break;
      }

      cursor = endIndex + endMarker.length;
      privateKeyBegin.lastIndex = cursor;
      match = privateKeyBegin.exec(value);
    }

    privateKeyBegin.lastIndex = 0;
    return output + value.slice(cursor);
  }

  function redactString(value) {
    const redacted = redactPrivateKeys(value)
      .replace(/(bearer\s+)[a-z0-9._~+\/-]+/gi, "$1[REDACTED]")
      .replace(/([?&](?:password|passwd|secret|token|access_token|api_key|key|signature|sig)=)[^&#\s]+/gi, "$1[REDACTED]");
    return redacted.length > maxStringLength ? `${redacted.slice(0, maxStringLength)}… [truncated]` : redacted;
  }

  function redact(value, depth = 0, seen = new WeakSet()) {
    if (typeof value === "string") return redactString(value);
    if (value === null || typeof value !== "object") return value;
    if (depth >= maxDepth) return "[MAX DEPTH]";
    if (seen.has(value)) return "[CIRCULAR]";

    seen.add(value);
    if (Array.isArray(value)) {
      const output = value.slice(0, maxEntries).map((item) => redact(item, depth + 1, seen));
      if (value.length > maxEntries) output.push(`[${value.length - maxEntries} more items]`);
      seen.delete(value);
      return output;
    }

    const entries = Object.entries(value).slice(0, maxEntries);
    const output = /** @type {Record<string, unknown>} */ ({});
    for (const [key, item] of entries) {
      output[key] = sensitiveKey.test(key) ? "[REDACTED]" : redact(item, depth + 1, seen);
    }
    if (Object.keys(value).length > maxEntries) output.__truncated__ = `${Object.keys(value).length - maxEntries} more keys`;
    seen.delete(value);
    return output;
  }

  function stringify(value) {
    try {
      return JSON.stringify(redact(value), null, 2);
    } catch {
      return redactString(String(value));
    }
  }

  function requestPath(url) {
    try {
      return new URL(String(url), "http://panel.local").pathname;
    } catch {
      return String(url || "").split("?", 1)[0];
    }
  }

  function renderHistory() {
    const target = document.getElementById("response-area");
    if (target) target.textContent = history.length ? stringify(history) : "No request has been recorded on this page.";
  }

  function record(value = {}) {
    const request = value.request || {};
    const response = value.response || {};
    const entry = redact({
      timestamp: value.timestamp || new Date().toISOString(),
      method: String(request.method || "GET").toUpperCase(),
      path: requestPath(request.url || request.path),
      status: response.status ?? null,
      request: { body: request.body ?? null },
      response: { data: response.data ?? null },
      background: value.background === true,
    });

    // Automatic refreshes must never replace or evict operator-requested evidence.
    if (entry.background) return entry;

    history.unshift(entry);
    if (history.length > maxHistoryEntries) history.length = maxHistoryEntries;
    renderHistory();
    return entry;
  }

  function records() {
    return redact(history);
  }

  function render(value) {
    if (value?.request && value?.response) return record(value);
    const target = document.getElementById("response-area");
    if (target) target.textContent = stringify(value);
    return value;
  }

  (/** @type {any} */ (window)).NO_PANEL_DIAGNOSTICS = { record, records, redact, render, stringify };
})();
