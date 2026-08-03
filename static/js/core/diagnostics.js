(() => {
  "use strict";

  const sensitiveKey = /(authorization|cookie|credential|password|passwd|private.?key|secret|session|token|webhook|api.?key)/i;
  const maxDepth = 6;
  const maxEntries = 50;
  const maxStringLength = 4000;

  function redactString(value) {
    const truncated = value.length > maxStringLength ? `${value.slice(0, maxStringLength)}… [truncated]` : value;
    return truncated
      .replace(/(bearer\s+)[a-z0-9._~+\/-]+/gi, "$1[REDACTED]")
      .replace(/([?&](?:password|secret|token|api_key)=)[^&#\s]+/gi, "$1[REDACTED]")
      .replace(/(-----BEGIN [^-]*PRIVATE KEY-----)[\s\S]*?(-----END [^-]*PRIVATE KEY-----)/gi, "$1\n[REDACTED]\n$2");
  }

  function redact(value, depth = 0, seen = new WeakSet()) {
    if (typeof value === "string") return redactString(value);
    if (value === null || typeof value !== "object") return value;
    if (depth >= maxDepth) return "[MAX DEPTH]";
    if (seen.has(value)) return "[CIRCULAR]";
    seen.add(value);
    if (Array.isArray(value)) {
      const items = value.slice(0, maxEntries).map((item) => redact(item, depth + 1, seen));
      if (value.length > maxEntries) items.push(`[${value.length - maxEntries} more items]`);
      return items;
    }
    const entries = Object.entries(value).slice(0, maxEntries);
    const output = {};
    for (const [key, item] of entries) {
      output[key] = sensitiveKey.test(key) ? "[REDACTED]" : redact(item, depth + 1, seen);
    }
    if (Object.keys(value).length > maxEntries) output.__truncated__ = `${Object.keys(value).length - maxEntries} more keys`;
    return output;
  }

  function stringify(value) {
    try {
      return JSON.stringify(redact(value), null, 2);
    } catch {
      return redactString(String(value));
    }
  }

  function render(value) {
    const target = document.getElementById("response-area");
    if (target) target.textContent = stringify(value);
  }

  (/** @type {any} */ (window)).NO_PANEL_DIAGNOSTICS = { redact, render, stringify };
})();
