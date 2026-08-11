// Modern UI client for the Flask endpoints.
// Keeps same endpoint names as the original panel.
// Adds: Ports tab + Server Settings (startup settings + DedicatedServerConfig editor).

const responseArea = document.getElementById("response-area");
const meta = document.getElementById("cmd-meta");
const pill = document.getElementById("pill");
const pageStatus = document.getElementById("page-status");
const portSelect = document.getElementById("server-port"); // legacy (removed from UI)
const serverSelector = document.getElementById("server-selector");
const serverSelectorHint = document.getElementById("server-selector-hint");
const copyBtn = document.getElementById("copy-btn");
/**
 * @typedef {Object} PanelContext
 * @property {"global"|"server"} [scope]
 * @property {string|null} [serverId]
 * @property {string} [activePage]
 * @property {string} [serversPath]
 */
/** @type {PanelContext} */
const panelContext = /** @type {Window & typeof globalThis & {NO_PANEL_CONTEXT?: PanelContext}} */ (window).NO_PANEL_CONTEXT || {};
const panelStatus = (/** @type {any} */ (window)).NO_PANEL_STATUS;
const panelDialog = (/** @type {any} */ (window)).NO_PANEL_DIALOG;
const panelDiagnostics = (/** @type {any} */ (window)).NO_PANEL_DIAGNOSTICS;

function notify(message, level="status", field=null){
  if(field && level === "error"){
    panelStatus?.fieldError(field, message);
    return;
  }
  panelStatus?.show(message, {level, focus: level === "error"});
}

async function confirmAction(options){
  if(!panelDialog){
    notify("Confirmation controls are unavailable. Reload the page and try again.", "error");
    return false;
  }
  return panelDialog.confirm(options);
}

async function promptAction(options){
  if(!panelDialog){
    notify("Input controls are unavailable. Reload the page and try again.", "error");
    return null;
  }
  return panelDialog.prompt(options);
}

// -----------------------------
// Multi-server selection state
// -----------------------------
let serversCache = [];
let currentServerId = panelContext.scope === "server" ? panelContext.serverId : null;

function isSelectedServerRemote(){
  const s = getSelectedServer();
  return !!(s && String(s.location || "").toLowerCase() === "remote");
}

function escapeHtml(s){
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}


function escapeAttr(s){
  // Safe for putting inside HTML attributes
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getSelectedServer(){
  return serversCache.find(s => String(s.id) === String(currentServerId)) || null;
}

function setSelectedServer(id){
  const targetId = String(id || "").trim();
  if (!targetId) return;
  if (panelContext.scope === "server" && targetId === String(currentServerId || "")) {
    return;
  }
  window.location.assign(`/servers/${encodeURIComponent(targetId)}`);
}

function withServerId(url){
  if (panelContext.scope !== "server" || !currentServerId) return url;

  // Never attach server_id to panel-global endpoints.
  // These must behave the same regardless of the selected server pill.
  try {
    const u = new URL(url, window.location.origin);
    const p = u.pathname || "";
    const noServerId =
      p.startsWith("/api/cluster") ||
      p.startsWith("/api/discord") ||
      p.startsWith("/api/auth") ||
      p.startsWith("/api/panel_users") ||
      p.startsWith("/api/whoami");
    if (noServerId) return url;
  } catch (e) {
    // if URL parsing fails, fall back to string checks below
    const s = String(url || "");
    if (s.includes("/api/cluster") || s.includes("/api/discord") || s.includes("/api/auth") || s.includes("/api/panel_users") || s.includes("/api/whoami")) {
      return url;
    }
  }

  // only add if not already specified
  if (String(url).includes("server_id=")) return url;

  const sep = String(url).includes("?") ? "&" : "?";
  return `${url}${sep}server_id=${encodeURIComponent(currentServerId)}`;
}

function setPageStatus(message, level="status"){
  panelStatus?.show(message, {level, target: pageStatus});
}

// -----------------------------
// Page registry (dynamic so missing pages don't crash)
// -----------------------------
const pages = {
  dashboard: {
    title: "Dashboard",
    sub: "Quick actions + live responses",
    el: document.getElementById("page-dashboard"),
  },
  control: {
    title: "Commands",
    sub: "Mission & server controls",
    el: document.getElementById("page-control"),
  },
  bans: {
    title: "Bans & Kicks",
    sub: "Manage kicked / banned players",
    el: document.getElementById("page-bans"),
  },
  ports: {
    title: "Ports",
    sub: "Manage ports and server names",
    el: document.getElementById("page-ports"),
  },
  moderation: {
    title: "Moderation",
    sub: "Friendly-fire settings and notifications",
    el: document.getElementById("page-moderation"),
  },
  manage: {
    title: "Server Deployment",
    sub: "Deploy, delete, and select server instances",
    el: document.getElementById("page-manage"),
  },
  // New page (only if your template adds it)
  server: {
    title: "Server Settings",
    sub: "Config + startup (FPS / Remote Commands Port)",
    el: document.getElementById("page-server"),
  },
  noblackbox: {
    title: "NoBlackBox",
    sub: "Install + configure Tacview recording",
    el: document.getElementById("page-noblackbox"),
  },
  gallery: {
    title: "Gallery",
    sub: "Browse NOBlackBox recordings",
    el: document.getElementById("page-gallery"),
  },
  about: {
    title: "About",
    sub: "How the panel talks to the server",
    el: document.getElementById("page-about"),
  },
  users: {
    title: "Panel Users",
    sub: "Accounts, failed logins, and IP blocks",
    el: document.getElementById("page-users"),
  },
  cluster: {
    title: "Cluster Setup",
    sub: "Create or join a LAN cluster",
    el: document.getElementById("page-cluster"),
  },

  discord: {
    title: "Discord Bot",
    sub: "Control the panel via Discord",
    el: document.getElementById("page-discord")
  },
};

// Drop any undefined pages to avoid errors
Object.keys(pages).forEach(k => {
  if (!pages[k].el) delete pages[k];
});

function initializePage(key){
  if (!pages[key]) return;

  // Bans page: show player pills to avoid typing SteamIDs
  if (key === "gallery"){
    wireGalleryUI();
    renderGalleryServers();
    galleryLoadFiles();
  }

  if (key === "bans"){
    wireBansPlayerUI();
    fetchPlayersForBans();
  }

  // page-specific loaders
  if (key === "users") loadPanelUsers();
  if (key === "cluster") loadClusterPage();
  if (key === "discord") (window.__discordRefreshStatus || window.refreshDiscordStatus)?.();
  if (key === "noblackbox") (window.loadNoBlackBox || (()=>{}))();
  if (key === "moderation") (window.loadModerationPage || (()=>{}))();
}

function diagnosticRequestBody(body){
  if(typeof body !== "string") return body || null;
  try { return JSON.parse(body); } catch { return body; }
}

/**
 * @param {string} url
 * @param {RequestInit & {background?: boolean, diagnostics?: boolean}} [opts]
 */
async function apiFetch(url, opts={}){
  const { background = false, diagnostics = true, ...fetchOpts } = opts;
  const effectiveUrl = withServerId(url);
  const r = await fetch(effectiveUrl, {
    credentials: "same-origin",
    ...fetchOpts,
    headers: {
      "Content-Type": "application/json",
      ...(fetchOpts.headers || {}),
    },
  });
  // If the session expired (e.g., panel restarted), bounce to login.
  if (r.status === 401) {
    try { window.location.href = "/login"; } catch {}
  }
  let data = null;
  try { data = await r.json(); } catch(e){ data = null; }
  if (diagnostics) {
    panelDiagnostics?.record({
      background,
      request: {method: fetchOpts.method || "GET", url: effectiveUrl, body: diagnosticRequestBody(fetchOpts.body)},
      response: {status: r.status, data},
    });
  }
  return { ok: r.ok, status: r.status, data };
}
(/** @type {any} */ (window)).apiFetch = apiFetch;

async function loadWhoAmI(){
  const me = await apiFetch("/api/whoami", { background: true });
  if (me.ok && me.data?.success){
    const el = document.getElementById("current-user");
    if (el) el.textContent = `${me.data.username || ""} (${me.data.role || ""})`;
  }
}

function setText(el, txt){ if(el) el.textContent = txt ?? ""; }

function renderList(container, itemsHtml){
  if (!container) return;
  container.innerHTML = itemsHtml || '<div class="muted small">None</div>';
}

async function loadPanelUsers(){
  const adminOnly = document.getElementById("users-admin-only");
  const panel = document.getElementById("users-panel");

  const res = await apiFetch("/api/panel-users");
  if (!res.ok){
    if (adminOnly) adminOnly.hidden = false;
    if (panel) panel.hidden = true;
    return;
  }
  if (adminOnly) adminOnly.hidden = true;
  if (panel) panel.hidden = false;

  const { users, attempts, blocked, is_local } = res.data;

  // users list
  const usersList = (users || []).map(u => {
    const uname = escapeHtml(u.username);
    const role = escapeHtml(u.role);
    const created = escapeHtml(u.created_at || "");
    return `
      <div class="row list-row">
        <div>
          <div class="text-strong">${uname} <span class="muted small">(${role})</span></div>
          <div class="muted small">Created: ${created}${u.must_change_password ? " • must change password" : ""}</div>
        </div>
        <div class="row actions">
          <button class="btn ghost" data-reset-user="${escapeAttr(u.username)}">Reset Password</button>
          <button class="btn danger" data-del-user="${escapeAttr(u.username)}">Delete</button>
        </div>
      </div>
    `;
  }).join("");
  renderList(document.getElementById("users-list"), usersList);

  // attempts list
  const attemptsHtml = (attempts || []).slice().reverse().map(a => {
    const ok = a.success ? "SUCCESS" : "FAIL";
    return `<div class="muted small list-copy">
      <b>${escapeHtml(ok)}</b> • ${escapeHtml(a.time)} • ${escapeHtml(a.ip)} • ${escapeHtml(a.username)}
    </div>`;
  }).join("");
  renderList(document.getElementById("login-attempts"), attemptsHtml);

  // blocked list
  const blockedHtml = (blocked || []).slice().reverse().map(b => {
    return `<div class="row list-row list-row--compact">
      <div class="muted small"><b>${escapeHtml(b.ip)}</b> • ${escapeHtml(b.blocked_at)} • ${escapeHtml(b.reason||"")}</div>
      <button class="btn ghost" data-unblock-ip="${escapeAttr(b.ip)}">Unblock</button>
    </div>`;
  }).join("");
  renderList(document.getElementById("blocked-ips"), blockedHtml);

  // localhost-only audit buttons
  const auditHint = document.getElementById("audit-localhint");
  setText(auditHint, is_local ? "Localhost access: allowed" : "Localhost access required (127.0.0.1)");
  const viewBtn = document.getElementById("audit-view-btn");
  const clearBtn = document.getElementById("audit-clear-btn");
  if (viewBtn) viewBtn.disabled = !is_local;
  if (clearBtn) clearBtn.disabled = !is_local;

  // wire actions
  const createBtn = document.getElementById("create-user-btn");
  if (createBtn && !createBtn.dataset.wired){
    createBtn.dataset.wired = "1";
    createBtn.addEventListener("click", async () => {
      const username = document.getElementById("new-user-name")?.value?.trim();
      const password = document.getElementById("new-user-pass")?.value || "";
      const role = document.getElementById("new-user-role")?.value || "mod";
      const r = await apiFetch("/api/panel-users", { method:"POST", body: JSON.stringify({username, password, role}) });
      if (!r.ok) notify(r.data?.error || "Create failed", "error", document.getElementById("new-user-name"));
      else {
        document.getElementById("new-user-name").value = "";
        document.getElementById("new-user-pass").value = "";
        await loadPanelUsers();
      }
    });
  }

  document.querySelectorAll("[data-reset-user]").forEach(btn => {
    btn.onclick = async () => {
      const u = btn.getAttribute("data-reset-user");
      const pw = await promptAction({
        title: "Reset user password",
        message: `Set a new password for ${u}.`,
        label: "New password",
        inputType: "password",
        autocomplete: "new-password",
        minLength: 6,
        confirmLabel: "Reset password",
      });
      if (!pw) return;
      const r = await apiFetch("/api/panel-users/reset-password", { method:"POST", body: JSON.stringify({username:u, password:pw}) });
      if (!r.ok) notify(r.data?.error || "Reset failed", "error");
      else await loadPanelUsers();
    };
  });

  document.querySelectorAll("[data-del-user]").forEach(btn => {
    btn.onclick = async () => {
      const u = btn.getAttribute("data-del-user");
      if (!await confirmAction({
        title: "Delete panel user",
        message: `Delete ${u}? This account will immediately lose panel access.`,
        confirmLabel: "Delete user",
        tone: "danger",
        requireText: u,
      })) return;
      const r = await apiFetch(`/api/panel-users/${encodeURIComponent(u)}`, { method:"DELETE" });
      if (!r.ok) notify(r.data?.error || "Delete failed", "error");
      else await loadPanelUsers();
    };
  });

  document.querySelectorAll("[data-unblock-ip]").forEach(btn => {
    btn.onclick = async () => {
      const ip = btn.getAttribute("data-unblock-ip");
      const r = await apiFetch("/api/panel-users/unblock", { method:"POST", body: JSON.stringify({ip}) });
      if (!r.ok) notify(r.data?.error || "Unblock failed", "error");
      else await loadPanelUsers();
    };
  });

  const auditOut = document.getElementById("audit-output");
  const auditView = document.getElementById("audit-view-btn");
  const auditClear = document.getElementById("audit-clear-btn");
  if (auditView && !auditView.dataset.wired){
    auditView.dataset.wired="1";
    auditView.addEventListener("click", async ()=>{
      const r = await apiFetch("/api/audit-logs");
      if (!r.ok) { notify(r.data?.error || "Audit fetch failed", "error"); return; }
      const lines = (r.data.logs || []).map(x => panelDiagnostics?.stringify(x) || String(x)).join("\n");
      auditOut.textContent = lines || "";
    });
  }
  if (auditClear && !auditClear.dataset.wired){
    auditClear.dataset.wired="1";
    auditClear.addEventListener("click", async ()=>{
      if (!await confirmAction({
        title: "Delete all audit logs",
        message: "This permanently removes the current file-backed audit history.",
        confirmLabel: "Delete audit logs",
        tone: "danger",
        requireText: "DELETE LOGS",
      })) return;
      const r = await apiFetch("/api/audit-logs", { method:"DELETE" });
      if (!r.ok) { notify(r.data?.error || "Audit clear failed", "error"); return; }
      if (auditOut) auditOut.textContent = "";
      notify("Audit logs cleared.", "success");
    });
  }
}


function ts(){
  const d = new Date();
  return d.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit", second:"2-digit"});
}

function setMeta(cmdName, status){
  if (!meta) return;
  meta.textContent = `${cmdName} • ${status} • ${ts()}`;
}

// Append a short status line to the live response area without risking runtime errors.
// Used by missions/password saves.
function pushResponse(msg){
  if(!responseArea) return;
  const line = `[${ts()}] ${msg}`;
  const cur = responseArea.textContent || "";
  const safeLine = String(panelDiagnostics?.redact(line) || line);
  responseArea.textContent = cur ? (safeLine + "\n" + cur) : safeLine;
}

// Back-compat helper used by some feature modules (e.g., Discord bot).
// Safely replaces the response panel contents.
function setResponse(val){
  if(!responseArea) return;
  responseArea.textContent = panelDiagnostics?.stringify(val) || String(val);
}

// -----------------------------
// Core POST helper for commands
// -----------------------------
async function sendCommand(endpoint, body){
  const s = getSelectedServer();
  if (!s){
    const msg = "No server selected. Create your first server (Server Management tab) and select it.";
    if (pill) pill.textContent = "Ready";
    setMeta(endpoint.split("/").pop(), "blocked");
    setResponse(msg);
    setPageStatus(msg, "error");
    return {success:false, error: msg};
  }

  const port = parseInt(String(s.remote_commands_port || ""), 10);
  if (!port){
    const msg = "Selected server has no Remote Commands Port configured. Edit it in Server Settings or recreate the server.";
    if (pill) pill.textContent = "Ready";
    setMeta(endpoint.split("/").pop(), "blocked");
    setResponse(msg);
    setPageStatus(msg, "error");
    return {success:false, error: msg};
  }

  const cmdName = endpoint.split("/").pop();

  if (pill) pill.textContent = "Working…";
  setPageStatus("");
  setMeta(cmdName, `${escapeHtml(s.name)} • port ${port}`);

  if (responseArea){
    setResponse(`Server: ${s.name} (Remote Commands: ${port})\nLoading…`);
  }

  try{
    const payload = Object.assign({}, body || {});
    payload.server_port = port;
    if (currentServerId && !payload.server_id) payload.server_id = currentServerId;

    const res = await fetch(withServerId(endpoint), {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload),
    });

    const data = await res.json().catch(() => ({}));
    const queued = Boolean(data.success && data.job?.id);
    if (pill) pill.textContent = queued ? "Queued" : (data.success ? "Done" : "Error");
    setMeta(cmdName, queued ? "queued" : (data.success ? "ok" : "error"));

    panelDiagnostics?.render({
      request: {method: "POST", url: withServerId(endpoint), body: payload},
      response: {status: res.status, data},
    });
    setPageStatus(
      data.success
        ? (queued ? `${cmdName} queued for ${s.name}. It will continue if this page closes.` : `${cmdName} completed for ${s.name}.`)
        : `${cmdName} failed for ${s.name}: ${data.error || "Unknown error"}`,
      data.success ? "status" : "error",
    );
    if (queued) {
      setResponse(`Job queued: ${data.job.id}\nTrack it at /servers/${encodeURIComponent(s.id)}/jobs`);
    }
    return data;
  }catch(err){
    if (pill) pill.textContent = "Error";
    setMeta(cmdName, "error");
    setResponse(String(err));
    setPageStatus(`${cmdName} failed for ${s.name}: ${String(err)}`, "error");
    return {success:false, error:String(err)};
  }
}


async function sendLocal(endpoint, body){
  const s = getSelectedServer();
  if (!s){
    const msg = "No server selected. Create your first server (Server Management tab) and select it.";
    if (pill) pill.textContent = "Ready";
    setMeta(endpoint.split("/").pop(), "blocked");
    setResponse(msg);
    setPageStatus(msg, "error");
    return {success:false, error: msg};
  }

  const cmdName = endpoint.split("/").pop();

  if (pill) pill.textContent = "Working…";
  setPageStatus("");
  setMeta(cmdName, `${escapeHtml(s.name)}`);
  if (responseArea){
    setResponse(`Server: ${s.name}\nLoading…`);
  }

  try{
    const payload = Object.assign({}, body || {});
    if (currentServerId && !payload.server_id) payload.server_id = currentServerId;

    const res = await fetch(withServerId(endpoint), {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload),
    });

    const data = await res.json().catch(() => ({}));
    if (pill) pill.textContent = data.success ? "Done" : "Error";
    setMeta(cmdName, data.success ? "ok" : "error");

    panelDiagnostics?.render({
      request: {method: "POST", url: withServerId(endpoint), body: payload},
      response: {status: res.status, data},
    });
    setPageStatus(
      data.success
        ? `${cmdName} completed for ${s.name}.`
        : `${cmdName} failed for ${s.name}: ${data.error || "Unknown error"}`,
      data.success ? "status" : "error",
    );
    return data;
  }catch(err){
    if (pill) pill.textContent = "Error";
    setMeta(cmdName, "error");
    setResponse(String(err));
    setPageStatus(`${cmdName} failed for ${s.name}: ${String(err)}`, "error");
    return {success:false, error:String(err)};
  }
}
// One-click commands
const commandConfirmations = {
  "clear-kicked-players": {
    title: "Clear kicked players",
    message: "Remove every player from the selected server's kicked list?",
    confirmLabel: "Clear kicked list",
    tone: "danger",
  },
  "banlist-clear": {
    title: "Clear ban list",
    message: "Remove every player from the selected server's ban list?",
    confirmLabel: "Clear ban list",
    tone: "danger",
    requireText: "CLEAR BANS",
  },
};

document.querySelectorAll("[data-command]").forEach(btn => {
  btn.addEventListener("click", async () => {
    const cmd = btn.getAttribute("data-command");
    if (commandConfirmations[cmd] && !await confirmAction(commandConfirmations[cmd])) return;
    const body = {};

    // Support simple payload attributes for quick-action buttons
    if (btn.hasAttribute("data-time")) {
      const t = parseFloat(btn.getAttribute("data-time"));
      if (!Number.isNaN(t)) body.time = t;
    }
    if (btn.hasAttribute("data-payload")) {
      try {
        const extra = JSON.parse(btn.getAttribute("data-payload") || "{}");
        if (extra && typeof extra === "object") Object.assign(body, extra);
      } catch (_) {}
    }

    sendCommand(`/command/${cmd}`, body);
  });
});

// Forms
function wireForm(id, endpoint, mapper, confirmation=null){
  const form = document.getElementById(id);
  if(!form) return;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const body = mapper(fd);
    if(confirmation){
      const options = typeof confirmation === "function" ? confirmation(body) : confirmation;
      if(!await confirmAction(options)) return;
    }
    sendCommand(endpoint, body);
  });
}


// ---------------- Gallery (NOBlackBox recordings) ----------------
let gallerySelectedServerId = null;

function _getServerById(id){
  return (serversCache || []).find(s => String(s.id) === String(id));
}

function renderGalleryServers(){
  const wrap = document.getElementById("gallery-servers");
  if(!wrap) return;
  wrap.innerHTML = "";

  const servers = (serversCache || []);
  if(!servers.length){
    wrap.innerHTML = '<div class="muted small">No servers configured.</div>';
    return;
  }

  // default selection
  if(!gallerySelectedServerId){
    gallerySelectedServerId = (currentServerId || servers[0].id);
  }
  if(gallerySelectedServerId && !servers.find(s => s.id === gallerySelectedServerId)){
    gallerySelectedServerId = servers[0].id;
  }

  servers.forEach(s => {
    const el = document.createElement("div");
    el.className = "player-pill gallery-server-pill" + (s.id === gallerySelectedServerId ? " selected" : "");
    el.innerHTML = `<div class="p-name" title="${escapeHtml(s.name || s.id)}">${escapeHtml(s.name || "Server")}</div><div class="p-sep">-</div><div class="p-id">${escapeHtml(String(s.location||"local").toUpperCase())}</div>`;
    el.addEventListener("click", async () => {
      wrap.querySelectorAll(".player-pill").forEach(x => x.classList.remove("selected"));
      el.classList.add("selected");
      gallerySelectedServerId = s.id;
      await galleryLoadFiles();
    });
    wrap.appendChild(el);
  });
}

function renderGalleryFiles(files){
  const wrap = document.getElementById("gallery-files");
  if(!wrap) return;

  const rows = (files || []).map(f => {
    const name = escapeHtml(f.name || "");
    const mtime = escapeHtml(f.mtime || "");
    const size = typeof f.size === "number" ? (Math.round((f.size/1024/1024)*10)/10 + " MB") : "";
    return `<tr data-name="${name}">
      <td class="table-col-name">${name}</td>
      <td class="table-col-date">${mtime}</td>
      <td class="table-col-size">${escapeHtml(size)}</td>
      <td class="table-col-actions">
        <div class="actions actions--end">
          <button class="btn ghost btn-sm gallery-open" data-name="${name}">View in program</button>
          <button class="btn ghost btn-sm gallery-path" data-name="${name}">Go to file path</button>
        </div>
      </td>
    </tr>`;
  }).join("");

  wrap.innerHTML = `
    <div class="table">
      <table>
        <thead>
          <tr>
            <th>File</th>
            <th>Created</th>
            <th>Size</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${rows || `<tr><td colspan="4" class="muted small">No recordings found.</td></tr>`}
        </tbody>
      </table>
    </div>
  `;

  // bind open buttons
  wrap.querySelectorAll(".gallery-open").forEach(btn => {
    btn.addEventListener("click", async (ev) => {
      const name = btn.getAttribute("data-name") || "";
      if(!name) return;
      await galleryFetchThenOpen(name, btn);
    });
  });
  wrap.querySelectorAll(".gallery-path").forEach(btn => {
    btn.addEventListener("click", async () => {
      const name = btn.getAttribute("data-name") || "";
      if(!name) return;
      await galleryOpenPath(name, btn);
    });
  });
}

async function galleryLoadFiles(){
  const status = document.getElementById("gallery-status");
  const sid = gallerySelectedServerId || currentServerId;
  if(!sid){
    if(status) status.textContent = "No server selected.";
    renderGalleryFiles([]);
    return;
  }
  if(status) status.textContent = "Loading recordings…";
  try{
    const j = await apiGet(`/api/gallery/list?server_id=${encodeURIComponent(String(sid))}`);
    if(!j || !j.success){
      if(status) status.textContent = (j && j.error) ? j.error : "Failed to load recordings.";
      renderGalleryFiles([]);
      return;
    }
    const outp = j.output_path ? `OutputPath: ${j.output_path}` : "";
    if(status) status.textContent = outp;
    renderGalleryFiles(j.files || []);
  }catch(e){
    if(status) status.textContent = "Failed to load recordings.";
    renderGalleryFiles([]);
  }
}

async function galleryFetchThenOpen(name, btnEl){
  const sid = gallerySelectedServerId || currentServerId;
  const status = document.getElementById("gallery-status");
  const s = _getServerById(sid);
  const isRemote = s && String(s.location||"").toLowerCase() === "remote";

  if(isRemote){
    if(status) status.textContent = "Fetching from remote server… Please wait (do not click again until complete).";
    try{
      if(btnEl){ btnEl.disabled = true; btnEl.textContent = "Fetching…"; }
      const j = await apiPost("/api/gallery/fetch", { server_id: sid, name: name });
      if(!j || !j.success){
        if(status) status.textContent = (j && j.error) ? j.error : "Fetch failed.";
        if(btnEl){ btnEl.disabled = false; btnEl.textContent = "View in program"; }
        return;
      }
      if(status) status.textContent = "Download complete. Opening…";
    }catch(e){
      if(status) status.textContent = "Fetch failed.";
      if(btnEl){ btnEl.disabled = false; btnEl.textContent = "View in program"; }
      return;
    }
  }

  // Open locally (for remote this uses the cached copy)
  await galleryOpenFile(name);

  if(btnEl){
    btnEl.disabled = false;
    btnEl.textContent = "View in program";
  }
}

async function galleryOpenFile(name){
  const sid = gallerySelectedServerId || currentServerId;
  const status = document.getElementById("gallery-status");
  if(!sid) return;
  try{
    const j = await apiPost("/api/gallery/open", { server_id: sid, name: name });
    if(j && j.success){
      if(status) status.textContent = "Opened in Tacview (or your default ACMI viewer).";
    }else{
      if(status) status.textContent = (j && j.error) ? j.error : "Failed to open.";
    }
  }catch(e){
    if(status) status.textContent = "Failed to open.";
  }
}

async function galleryOpenPath(name, btnEl){
  const sid = gallerySelectedServerId || currentServerId;
  const status = document.getElementById("gallery-status");
  const s = _getServerById(sid);
  const isRemote = s && String(s.location||"").toLowerCase() === "remote";
  if(!sid) return;

  if(isRemote){
    if(status) status.textContent = "Fetching remote recording so its local file path can be opened…";
    try{
      if(btnEl){ btnEl.disabled = true; btnEl.textContent = "Fetching…"; }
      const j = await apiPost("/api/gallery/fetch", { server_id: sid, name: name });
      if(!j || !j.success){
        if(status) status.textContent = (j && j.error) ? j.error : "Fetch failed.";
        if(btnEl){ btnEl.disabled = false; btnEl.textContent = "Go to file path"; }
        return;
      }
    }catch(e){
      if(status) status.textContent = "Fetch failed.";
      if(btnEl){ btnEl.disabled = false; btnEl.textContent = "Go to file path"; }
      return;
    }
  }

  try{
    if(btnEl){ btnEl.disabled = true; }
    const j = await apiPost("/api/gallery/open-path", { server_id: sid, name: name });
    if(j && j.success){
      const where = j.path || j.folder || "file location";
      if(status) status.textContent = `Opened file path: ${where}`;
    }else{
      if(status) status.textContent = (j && j.error) ? j.error : "Failed to open file path.";
    }
  }catch(e){
    if(status) status.textContent = "Failed to open file path.";
  }finally{
    if(btnEl){ btnEl.disabled = false; btnEl.textContent = "Go to file path"; }
  }
}

function wireGalleryUI(){
  const btn = document.getElementById("gallery-refresh");
  if(btn && btn.dataset.wired !== "1"){
    btn.dataset.wired = "1";
    btn.addEventListener("click", galleryLoadFiles);
  }
}

// ---------------- Bans/Kicks: Player pills ----------------
function _formatPlayerLine(p){
  if(!p || typeof p !== "object") return null;
  const name = String(
    p.displayName ?? p.DisplayName ?? p.username ?? p.name ?? p.player_name ?? p.PlayerName ?? p.Name ?? p.Display ?? p.Display_Name ?? ""
  ).trim() || "Player";
  const sid  = String(
    p.steamId ?? p.steamID ?? p.SteamId ?? p.SteamID ?? p.steam_id ?? p.steamid ?? p.steamId64 ?? p.id ?? p.Id ?? ""
  ).trim();
  if(!sid) return null;
  return { name, sid, label: `${name} - ${sid}` };
}

function _extractPlayers(raw){
  // The remote command may return players as an array, or a dict with a Players/players field.
  if(Array.isArray(raw)) return raw;
  if(raw && typeof raw === "object"){
    if(Array.isArray(raw.players)) return raw.players;
    if(Array.isArray(raw.Players)) return raw.Players;

    // common wrapper: { response: { Players: [...] }, status_code: "Success" }
    if(raw.response && typeof raw.response === "object"){
      if(Array.isArray(raw.response.players)) return raw.response.players;
      if(Array.isArray(raw.response.Players)) return raw.response.Players;
    }

    if(raw.body && typeof raw.body === "object"){
      if(Array.isArray(raw.body.players)) return raw.body.players;
      if(Array.isArray(raw.body.Players)) return raw.body.Players;
      if(raw.body.response && typeof raw.body.response === "object"){
        if(Array.isArray(raw.body.response.players)) return raw.body.response.players;
        if(Array.isArray(raw.body.response.Players)) return raw.body.response.Players;
      }
    }
  }
  return [];
}

function renderBansPlayerPills(players){
  const wrap = document.getElementById("bans-player-pills");
  const status = document.getElementById("bans-player-status");
  if(!wrap) return;

  wrap.innerHTML = "";
  const mapped = (players || []).map(_formatPlayerLine).filter(Boolean);

  if(status){
    status.textContent = mapped.length ? `Showing ${mapped.length} player(s).` : "No players found (or server returned an empty list).";
  }

  mapped.slice(0, 40).forEach(p => {
    const el = document.createElement("button");
    el.className = "player-entity";
    el.type = "button";
    el.dataset.sid = p.sid;
    el.setAttribute("aria-label", `Select ${p.name}, Steam ID ${p.sid}`);
    el.innerHTML = `<span class="p-name" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</span><span class="p-id">${escapeHtml(p.sid)}</span><span class="status-badge status-badge--success"><span class="status-dot" aria-hidden="true"></span>Connected</span><span class="p-action">Select</span>`;

    el.addEventListener("click", () => {
      // highlight selection
      wrap.querySelectorAll(".player-entity").forEach(x => x.classList.remove("selected"));
      el.classList.add("selected");

      // fill SteamID inputs in the existing forms
      const kickInput = document.querySelector('#kick-player-form input[name="steam_id"]');
      const unkickInput = document.querySelector('#unkick-player-form input[name="steam_id"]');
      const banInput = document.querySelector('#ban-player-form input[name="steam_id"]');
      const unbanInput = document.querySelector('#unban-player-form input[name="steam_id"]');
      [kickInput, unkickInput, banInput, unbanInput].forEach(inp => { if(inp) inp.value = p.sid; });
    });

    wrap.appendChild(el);
  });
}

async function fetchPlayersForBans(){
  const s = getSelectedServer();
  const status = document.getElementById("bans-player-status");
  if(!s){
    renderBansPlayerPills([]);
    if(status) status.textContent = "No server selected.";
    return;
  }

  const port = parseInt(String(s.remote_commands_port || ""), 10);
  if(!port){
    renderBansPlayerPills([]);
    if(status) status.textContent = "Selected server has no Remote Commands Port configured.";
    return;
  }

  if(status) status.textContent = "Loading players…";

  try{
    const payload = { server_port: port };
    if(currentServerId) payload.server_id = currentServerId;

    const res = await fetch(withServerId("/command/get-player-list"), {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload),
    });
    const j = await res.json().catch(()=> ({}));
    const ok = (j && (j.success === true || j.success === undefined) &&
                (j.status_code === undefined || String(j.status_code).toLowerCase() === "success" || String(j.status_code).toLowerCase() === "ok"));
    if(!j || !ok){
      renderBansPlayerPills([]);
      if(status) status.textContent = (j && (j.error || j.message)) ? (j.error || j.message) : "Failed to load players.";
      return;
    }

    const players = _extractPlayers(j.response ?? j.body ?? j.data ?? j);
    renderBansPlayerPills(players);
  }catch(e){
    renderBansPlayerPills([]);
    if(status) status.textContent = "Failed to load players.";
  }
}

function wireBansPlayerUI(){
  const btn = document.getElementById("bans-refresh-players");
  if(btn && btn.dataset.wired !== "1"){
    btn.dataset.wired = "1";
    btn.addEventListener("click", fetchPlayersForBans);
  }
}

wireForm("send-chat-message-form", "/command/send-chat-message", (fd)=>({message: fd.get("message")}));
wireForm("reload-config-form", "/command/reload-config", (fd)=>{
  const path = (fd.get("path") || "").toString().trim();
  return path ? {path} : {};
});
wireForm("set-time-remaining-form", "/command/set-time-remaining", (fd)=>({time: fd.get("time")}));
wireForm("set-next-mission-form", "/command/set-next-mission", (fd)=>({
  group: fd.get("group"),
  name: fd.get("name"),
  max_time: fd.get("max_time"),
}));
wireForm(
  "kick-player-form",
  "/command/kick-player",
  (fd)=>({steam_id: fd.get("steam_id")}),
  (body)=>({
    title: "Kick player",
    message: `Kick Steam ID ${body.steam_id || "(unknown)"} from the selected server?`,
    confirmLabel: "Kick player",
    tone: "danger",
  }),
);
wireForm("unkick-player-form", "/command/unkick-player", (fd)=>({steam_id: fd.get("steam_id")}));
wireForm(
  "ban-player-form",
  "/command/banlist-add",
  (fd)=>({steam_id: fd.get("steam_id"), reason: fd.get("reason")}),
  (body)=>({
    title: "Ban player",
    message: `Ban Steam ID ${body.steam_id || "(unknown)"} from the selected server?`,
    confirmLabel: "Ban player",
    tone: "danger",
  }),
);
wireForm("unban-player-form", "/command/banlist-remove", (fd)=>({steam_id: fd.get("steam_id")}));

copyBtn?.addEventListener("click", async () => {
  try{
    await navigator.clipboard.writeText(responseArea?.textContent || "");
    copyBtn.textContent = "Copied";
    setTimeout(()=>copyBtn.textContent="Copy", 900);
  }catch{
    // ignore
  }
});

// Update Server button -> local endpoint
document.getElementById("update-server-btn")?.addEventListener("click", async () => {
  if (!await confirmAction({
    title: "Update selected server",
    message: "This stops the selected server, updates it through SteamCMD, and starts it again.",
    confirmLabel: "Stop and update",
    tone: "danger",
  })) return;
  sendLocal("/local/update-server", {});
});

// Start/Stop/Restart buttons (act on selected server pill)
document.getElementById("start-server-btn")?.addEventListener("click", () => {
  sendLocal("/local/start-server", {});
});
document.getElementById("stop-server-btn")?.addEventListener("click", async () => {
  if (!await confirmAction({
    title: "Stop selected server",
    message: "Connected players will be disconnected.",
    confirmLabel: "Stop server",
    tone: "danger",
  })) return;
  sendLocal("/local/stop-server", {});
});
document.getElementById("restart-server-btn")?.addEventListener("click", async () => {
  if (!await confirmAction({
    title: "Restart selected server",
    message: "Connected players will be disconnected while the server restarts.",
    confirmLabel: "Restart server",
    tone: "danger",
  })) return;
  sendLocal("/local/restart-server", {});
});



// -----------------------------
// Ports tab (Game/Query ports editor)
// -----------------------------
async function fetchPorts(){
  const res = await fetch("/api/ports");
  const data = await res.json();
  if(!data.success) throw new Error(data.error || "Failed to load ports");
  return data.ports;
}

async function savePorts(ports){
  const res = await fetch("/api/ports", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ports})
  });
  const data = await res.json();
  if(!data.success) throw new Error(data.error || "Failed to save ports");
  return data.ports;
}

function escapeHtml(s){
  return (s ?? "").toString().replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

function refreshPortDropdown(ports){
  if(!portSelect) return;
  const current = portSelect.value;
  portSelect.innerHTML = "";
  // If there are no ports yet, force the user to create a server first.
  if (!ports || ports.length === 0){
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No ports available (create a server first)";
    portSelect.appendChild(opt);
    portSelect.disabled = true;
    return;
  }
  portSelect.disabled = false;
  for(const p of ports){
    const opt = document.createElement("option");
    opt.value = String(p.port);
    opt.textContent = `${p.name} (${p.port})`;
    portSelect.appendChild(opt);
  }
  if ([...portSelect.options].some(o => o.value === current)){
    portSelect.value = current;
  }
}

function renderPortsTable(ports){
  const tbody = document.querySelector("#ports-table tbody");
  if(!tbody) return;
  tbody.innerHTML = "";
  for(const p of ports){
    const tr = document.createElement("tr");
    const loc = (p.location === "remote") ? "remote" : "local";
    tr.dataset.serverId = String(p.id || "");
    tr.innerHTML = `
      <td>
        <div class="stack stack--tight">
          <div>${escapeHtml(p.name || "Unnamed")}</div>
          <div class="muted text-small">${escapeHtml(loc)}${p.node_id ? ` • ${escapeHtml(p.node_id)}` : ""}</div>
        </div>
      </td>
      <td><input class="input" value="${p.game_port ?? ""}" inputmode="numeric" placeholder="(blank = default)"></td>
      <td><input class="input" value="${p.query_port ?? ""}" inputmode="numeric" placeholder="(blank = default)"></td>
      <td></td>
    `;
    tbody.appendChild(tr);
  }
}

function readPortsFromTable(){
  const rows = [...document.querySelectorAll("#ports-table tbody tr")];
  return rows.map(r=>{
    const ins = r.querySelectorAll("input");
    return {
      id: String(r.dataset.serverId || ""),
      game_port: (ins[0].value||"").trim(),
      query_port: (ins[1].value||"").trim()
    };
  });
}

async function loadPortsAndRefreshUI(){
  const ports = await fetchPorts();
  renderPortsTable(ports);
  refreshPortDropdown(ports);
  return ports;
}

async function initPortsUI(){
  if(!document.getElementById("page-ports")) return;

  try{
    await loadPortsAndRefreshUI();
  }catch(e){
    console.error(e);
  }

  document.getElementById("refresh-ports")?.addEventListener("click", async ()=>{
    try{
      await loadPortsAndRefreshUI();
    }catch(e){
      notify(e.message || String(e), "error");
    }
  });

  document.getElementById("save-ports")?.addEventListener("click", async ()=>{
    try{
      const ports = readPortsFromTable();
      const saved = await savePorts(ports);
      renderPortsTable(saved);
      refreshPortDropdown(saved);
      notify("Ports saved.", "success");
    }catch(e){
      notify(e.message || String(e), "error");
    }
  });

  document.getElementById("cleanup-firewall")?.addEventListener("click", async ()=>{
    try{
      const ok = await confirmAction({
        title: "Clean up firewall rules",
        message: "Remove stale Windows Firewall rules created by this panel that are no longer needed for current cluster and server ports.",
        confirmLabel: "Remove stale rules",
        tone: "danger",
        requireText: "CLEANUP",
      });
      if(!ok) return;

      const res = await fetch("/api/firewall/cleanup", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({})
      });
      const data = await res.json().catch(()=>null);
      if(!res.ok || !data || !data.success){
        const msg = (data && (data.error || data.message)) || (await res.text().catch(()=>"")) || "Request failed";
        throw new Error(msg);
      }

      const removed = data.removed_count ?? 0;
      const kept = data.kept_count ?? 0;
      const sample = Array.isArray(data.removed) ? data.removed.slice(0, 20) : [];
      const extra = (Array.isArray(data.removed) && data.removed.length > 20) ? `\n...and ${data.removed.length - 20} more` : "";

      notify(
        `Firewall cleanup complete.\n\nRemoved: ${removed}\nKept: ${kept}` +
        (sample.length ? `\n\nRemoved rules (sample):\n- ${sample.join("\n- ")}${extra}` : ""),
        "success",
      );
    }catch(e){
      notify(e.message || String(e), "error");
    }
  });
}


// -----------------------------
// Server Settings (NEW)
// Requires these elements in the server settings template (ids):
// - #startup-fps
// - #startup-remote-port
// - #startup-load-btn
// - #startup-save-btn
// - #dedicated-config-text
// - #dedicated-load-btn
// - #dedicated-save-btn
// -----------------------------
async function apiGet(url){
  const res = await fetch(withServerId(url));
  const data = await res.json();
  return data;
}

// ---------------- Branding ----------------
function applyBrandingVars(branding){
  if(!branding) return;
  if(branding.accent){
    document.documentElement.style.setProperty("--color-accent", branding.accent);
    document.documentElement.style.setProperty("--accent", branding.accent);
  }
  if(branding.accent2){
    document.documentElement.style.setProperty("--color-accent-secondary", branding.accent2);
    document.documentElement.style.setProperty("--accent2", branding.accent2);
  }
}

function setBrandLogo(logoUrl){
  const img = document.getElementById("brand-logo-img");
  const svg = document.querySelector(".brand-mark svg");
  if(!img) return;
  if(logoUrl){
    img.src = logoUrl + "?v=" + Date.now();
    img.hidden = false;
    if(svg) svg.toggleAttribute("hidden", true);
  }else{
    img.removeAttribute("src");
    img.hidden = true;
    if(svg) svg.toggleAttribute("hidden", false);
  }
}

async function loadBranding(){
  try{
    const j = await apiGet("/api/branding");
    if(!j || !j.success) return;
    const b = j.branding || {};
    applyBrandingVars(b);

    const colorEl = document.getElementById("branding-accent");
    if(colorEl && b.accent) colorEl.value = b.accent;

    setBrandLogo(b.logo_url || null);
  }catch(e){}
}

async function saveBrandingColor(){
  const colorEl = document.getElementById("branding-accent");
  const statusEl = document.getElementById("branding-status");
  if(!colorEl) return;
  try{
    const accent = colorEl.value;
    const j = await apiPost("/api/branding", { accent: accent, accent2: accent });
    if(j && j.success){
      applyBrandingVars({accent: accent, accent2: accent});
      if(statusEl) statusEl.textContent = "Saved.";
    }else{
      if(statusEl) statusEl.textContent = (j && j.error) ? j.error : "Failed to save.";
    }
  }catch(e){
    if(statusEl) statusEl.textContent = "Failed to save.";
  }
}

async function uploadBrandLogo(){
  const fileEl = document.getElementById("branding-logo-file");
  const statusEl = document.getElementById("branding-status");
  if(!fileEl || !fileEl.files || !fileEl.files[0]){
    if(statusEl) statusEl.textContent = "Choose an image first.";
    return;
  }
  const fd = new FormData();
  fd.append("file", fileEl.files[0]);

  try{
    const resp = await fetch("/api/branding/logo", { method:"POST", body: fd, credentials:"include" });
    const j = await resp.json();
    if(j && j.success){
      if(statusEl) statusEl.textContent = "Logo updated.";
      await loadBranding();
    }else{
      if(statusEl) statusEl.textContent = (j && j.error) ? j.error : "Upload failed.";
    }
  }catch(e){
    if(statusEl) statusEl.textContent = "Upload failed.";
  }
}

async function resetBrandLogo(){
  const statusEl = document.getElementById("branding-status");
  if(!await confirmAction({
    title: "Reset panel logo",
    message: "Remove the uploaded logo and restore the built-in panel mark?",
    confirmLabel: "Reset logo",
    tone: "danger",
  })) return;
  try{
    const j = await apiPost("/api/branding/logo/reset", {});
    if(j && j.success){
      if(statusEl) statusEl.textContent = "Reset to default.";
      await loadBranding();
    }else{
      if(statusEl) statusEl.textContent = "Reset failed.";
    }
  }catch(e){
    if(statusEl) statusEl.textContent = "Reset failed.";
  }
}

function bindBrandingUI(){
  const saveBtn = document.getElementById("branding-save-color");
  const upBtn = document.getElementById("branding-upload-logo");
  const resetBtn = document.getElementById("branding-clear-logo");
  if(saveBtn) saveBtn.addEventListener("click", saveBrandingColor);
  if(upBtn) upBtn.addEventListener("click", uploadBrandLogo);
  if(resetBtn) resetBtn.addEventListener("click", resetBrandLogo);
}

async function apiPost(url, body){
  const payload = Object.assign({}, body || {});
  if (currentServerId && !payload.server_id) payload.server_id = currentServerId;
  const res = await fetch(withServerId(url), {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  return data;
}

function safeInt(v){
  const n = parseInt(String(v ?? "").trim(), 10);
  return Number.isFinite(n) ? n : null;
}

// -----------------------------
// MOTD (Message of the Day)
// -----------------------------
async function loadMotdIntoUI(){
  const tEl = document.getElementById("motd-text");
  const rEl = document.getElementById("motd-repeat");
  if(!tEl || !rEl) return;

  if(!currentServerId){
    tEl.value = "";
    rEl.value = "";
    return;
  }

  const j = await apiGet(`/api/server-motd?server_id=${encodeURIComponent(currentServerId)}`);
  if(!j.success){
    // Don't hard-fail the whole page if moderator/admin rules block it
    console.warn(j.error || "Failed to load MOTD");
    return;
  }
  tEl.value = j.motd?.text || "";
  const rm = j.motd?.repeat_minutes;
  rEl.value = (rm === null || rm === undefined) ? "" : String(rm);
}

async function saveMotdFromUI(){
  const tEl = document.getElementById("motd-text");
  const rEl = document.getElementById("motd-repeat");
  if(!tEl || !rEl) return;

  if(!currentServerId){
    notify("Create or select a server first.", "error");
    return;
  }

  const text = (tEl.value || "").trim();
  const rep = safeInt(rEl.value);
  const repeatMinutes = (rep === null) ? 0 : rep;
  if(repeatMinutes < 0){
    notify("Repeat minutes must be 0 or greater.", "error", rEl);
    return;
  }

  const j = await apiPost("/api/server-motd", {
    server_id: currentServerId,
    text,
    repeat_minutes: repeatMinutes,
  });
  if(!j.success){
    notify(j.error || "Failed to save MOTD", "error");
    return;
  }
  notify("MOTD saved.", "success");
  await loadMotdIntoUI();
}

async function loadStartupSettingsIntoUI(){
  const fpsEl = document.getElementById("startup-fps");
  const mpEl  = document.getElementById("startup-max-players");
  const portEl = document.getElementById("startup-remote-port");
  if(!fpsEl || !mpEl || !portEl) return;

  if (!currentServerId){
    fpsEl.value = "";
    mpEl.value = "";
    portEl.value = "";
    return;
  }

  const j = await apiGet("/api/startup-settings");
  if(!j.success){
    notify(j.error || "Failed to load startup settings", "error");
    return;
  }
  fpsEl.value = (j.settings?.fps ?? "") === null ? "" : (j.settings?.fps ?? "");
  mpEl.value  = (j.settings?.max_players ?? "") === null ? "" : (j.settings?.max_players ?? "");
  portEl.value = (j.settings?.remote_commands_port ?? "") === null ? "" : (j.settings?.remote_commands_port ?? "");
}

async function saveStartupSettingsFromUI(){
  const fpsEl = document.getElementById("startup-fps");
  const mpEl  = document.getElementById("startup-max-players");
  const portEl = document.getElementById("startup-remote-port");
  if(!fpsEl || !mpEl || !portEl) return;

  const fps = safeInt(fpsEl.value);
  const mp  = safeInt(mpEl.value);
  const rp = safeInt(portEl.value);

  if (fps !== null && (fps < 1 || fps > 1000)){
    notify("FPS must be between 1 and 1000.", "error", fpsEl);
    return;
  }
  if (mp !== null && (mp < 1 || mp > 256)){
    notify("Max Players must be between 1 and 256.", "error", mpEl);
    return;
  }
  if (rp !== null && (rp < 1 || rp > 65535)){
    notify("Remote Commands Port must be between 1 and 65535.", "error", portEl);
    return;
  }

  const oldPort = getSelectedServer() ? parseInt(String(getSelectedServer().remote_commands_port || ""), 10) : null;

const j = await apiPost("/api/startup-settings", {
  settings: {
    fps: fps,
    max_players: mp,
    remote_commands_port: rp,
    old_port: oldPort
  }
});

  if(!j.success){
    notify(j.error || "Failed to save startup settings", "error");
    return;
  }

  if(j.restart_required){
    notify(`Startup settings saved as v${j.config_version?.version?.version_number || "?"}. Restart required for FPS / Remote Command port changes to take effect.`, "status");
  }else{
    notify(`Startup settings saved as v${j.config_version?.version?.version_number || "?"}.`, "success");
  }

  // Remote Commands Port changes no longer affect the Ports tab (which is now Game/Query only).

  // Reload from server (shows normalized values)
  await loadStartupSettingsIntoUI();
}

async function loadDedicatedConfigIntoUI(){
  const txt = document.getElementById("dedicated-config-text");
  if(!txt) return;

  if (!currentServerId){
    txt.value = "// No server selected. Create/select a server in Server Management.";
    return;
  }

  if (!currentServerId){
    txt.value = "// No server configured yet.\n// Create your first server in the Server Management tab.\n";
    return;
  }

  const j = await apiGet("/api/dedicated-config");
  if(!j.success){
    notify(j.error || "Failed to load DedicatedServerConfig.json", "error");
    return;
  }
if(j.exists === false || j.config == null){
  txt.value = "// DedicatedServerConfig.json not generated yet.\n// Create/Start this server once (the panel will do a short first-boot on create) and reload.\n";
  return;
}
txt.value = JSON.stringify(j.config, null, 2);
}

async function saveDedicatedConfigFromUI(){
  const txt = document.getElementById("dedicated-config-text");
  if(!txt) return;

  let obj;
  try{
    obj = JSON.parse(txt.value);
  }catch(e){
    notify("Invalid JSON: " + (e?.message || e), "error", txt);
    return;
  }

  const j = await apiPost("/api/dedicated-config", { config: obj });
  if(!j.success){
    notify(j.error || "Failed to save DedicatedServerConfig.json", "error", txt);
    return;
  }

  notify(`DedicatedServerConfig.json saved as v${j.config_version?.version?.version_number || "?"}.`, "success");
  // (Optional) you can press Reload Config in Commands tab to apply some changes without restart.
}


async function loadPasswordIntoUI(){
  const pwEl = document.getElementById("server-password");
  const pwStatus = document.getElementById("password-status");
  if(!pwEl) return;
  if(!currentServerId){ pwEl.value=""; return; }

  const j = await apiGet("/api/dedicated-config");
  if(!j.success){ return; }
  const cfg = j.config || {};

  // SECURITY/UX: do not auto-fill the actual password back into the textbox.
  // Keep it empty after save, and only show whether a password is set.
  if(pwStatus){
    const hasPw = (cfg && typeof cfg.Password === "string" && cfg.Password.length > 0);
    pwStatus.textContent = hasPw ? "Password is set on this server." : "No password set.";
  }
  // Never overwrite the input value during auto-refresh
  if(document.activeElement !== pwEl){
    pwEl.value = "";
  }
}

async function savePasswordFromUI(){
  const pwEl = document.getElementById("server-password");
  if(!pwEl) return;
  if (!currentServerId){
    notify("Create or select a server first.", "error");
    return;
  }
  const res = await apiPost("/api/server-password", { server_id: currentServerId, password: pwEl.value || "" });
  if(!res.success){
    notify(res.error || "Failed to save password", "error", pwEl);
    return;
  }
  const msg = "Password saved. Restart the server for it to take effect.";
  // Clear the box immediately, then show the same styled notice as restart-required warnings.
  pwEl.value = "";
  try{ pwEl.dispatchEvent(new Event("input", { bubbles:true })); }catch{}
  pushResponse(msg);
  showSettingsNotice(msg);
  await loadPasswordIntoUI();
}

async function loadMissionsList(group){
  const g = group || "BuiltIn";
  const j = await apiGet(`/api/missions?group=${encodeURIComponent(g)}`);
  return j.success ? j : {success:false, missions:[], mission_dir:""};
}

function fillMissionSelect(selectEl, missions, selectedValue){
  if(!selectEl) return;
  const opts = [`<option value="">None</option>`]
    .concat((missions||[]).map(m => `<option value="${escapeAttr(m)}">${escapeHtml(m)}</option>`));
  selectEl.innerHTML = opts.join("");
  if(selectedValue != null){
    selectEl.value = selectedValue;
  }
}

function showSettingsNotice(msg){
  const el = document.getElementById("server-settings-notice");
  if(!el){
    notify(msg, "status");
    return;
  }
  el.textContent = msg || "";
  el.hidden = !msg;
}

async function loadMissionSlotsIntoUI(){
  const g1 = document.getElementById("mission1-group");
  const n1 = document.getElementById("mission1-name");
  const g2 = document.getElementById("mission2-group");
  const n2 = document.getElementById("mission2-name");
  const helpEl = document.getElementById("mission-help");
  if(!g1 || !n1 || !g2 || !n2) return;

  if(!currentServerId){
    g1.value = "BuiltIn"; g2.value = "BuiltIn";
    fillMissionSelect(n1, [], "");
    fillMissionSelect(n2, [], "");
    if(helpEl) helpEl.textContent = "Create/select a server to configure missions.";
    return;
  }

  const s = await apiGet("/api/mission-slots");
  if(!s.success){ return; }

  const slot1 = s.slot1 || {group:"BuiltIn", name:"", max_time:7200.0};
  const slot2 = s.slot2 || {group:"BuiltIn", name:"", max_time:7200.0};

  g1.value = slot1.group || "BuiltIn";
  g2.value = slot2.group || "BuiltIn";

  const list1 = await loadMissionsList(g1.value);
  const list2 = await loadMissionsList(g2.value);

  fillMissionSelect(n1, list1.missions || [], slot1.name || "");
  fillMissionSelect(n2, list2.missions || [], slot2.name || "");

  if(helpEl){
    const dir = s.mission_dir || "";
    helpEl.textContent = `User missions folder: ${dir}  •  Built-in missions use game content (no files).`;
  }
}

async function onMissionGroupChanged(slotIdx){
  const gEl = document.getElementById(slotIdx === 1 ? "mission1-group" : "mission2-group");
  const nEl = document.getElementById(slotIdx === 1 ? "mission1-name" : "mission2-name");
  if(!gEl || !nEl) return;

  const list = await loadMissionsList(gEl.value);
  // keep current selection if still valid
  const cur = nEl.value || "";
  fillMissionSelect(nEl, list.missions || [], cur);
}

async function saveMissionSlotsFromUI(){
  const g1 = document.getElementById("mission1-group");
  const n1 = document.getElementById("mission1-name");
  const g2 = document.getElementById("mission2-group");
  const n2 = document.getElementById("mission2-name");
  if(!g1 || !n1 || !g2 || !n2) return;

  if(!currentServerId){
    notify("Create or select a server first.", "error");
    return;
  }

  const payload = {
    server_id: currentServerId,
    slot1: { group: g1.value || "BuiltIn", name: n1.value || "" },
    slot2: { group: g2.value || "BuiltIn", name: n2.value || "" }
  };

  const res = await apiPost("/api/mission-slots", payload);
  if(!res.success){
    notify(res.error || "Failed to save missions", "error");
    return;
  }
  const msg = "Missions saved. Restart the server for them to take effect.";
  pushResponse(msg);
  showSettingsNotice(msg);
  await loadDedicatedConfigIntoUI();
}

async function initServerAccessUI(){
  const hasPasswordControls = Boolean(document.getElementById("server-password"));
  const hasMissionControls = Boolean(document.getElementById("mission1-group"));
  if(!hasPasswordControls && !hasMissionControls) return;

  document.getElementById("password-save-btn")?.addEventListener("click", savePasswordFromUI);
  document.getElementById("mission-slots-save-btn")?.addEventListener("click", saveMissionSlotsFromUI);
  document.getElementById("mission1-group")?.addEventListener("change", async () => { await onMissionGroupChanged(1); });
  document.getElementById("mission2-group")?.addEventListener("change", async () => { await onMissionGroupChanged(2); });

  await loadPasswordIntoUI();
  await loadMissionSlotsIntoUI();
}

async function initServerSettingsUI(){
  // Only run if the page exists in this build
  if(!document.getElementById("page-server")) return;

  document.getElementById("startup-load-btn")?.addEventListener("click", loadStartupSettingsIntoUI);
  document.getElementById("startup-save-btn")?.addEventListener("click", saveStartupSettingsFromUI);

  document.getElementById("motd-save-btn")?.addEventListener("click", saveMotdFromUI);

  document.getElementById("dedicated-load-btn")?.addEventListener("click", loadDedicatedConfigIntoUI);
  document.getElementById("dedicated-save-btn")?.addEventListener("click", saveDedicatedConfigFromUI);

  // Initial load for selected server
  await loadMotdIntoUI();

  // Auto-load once when the app starts, but only if a server is selected.
  if (currentServerId){
    await loadStartupSettingsIntoUI();
    await loadDedicatedConfigIntoUI();
    await loadMotdIntoUI();
  }
}



// -----------------------------
// Server Management
// -----------------------------
const smName = document.getElementById("sm-name");
const smRemotePort = document.getElementById("sm-remote-port");
const smGamePort = document.getElementById("sm-game-port");
const smQueryPort = document.getElementById("sm-query-port");
const smInstallDir = document.getElementById("sm-install-dir");
const smNode = document.getElementById("sm-node");
const smNodeNote = document.getElementById("sm-node-note");
const smCreate = document.getElementById("sm-create");
const smRefresh = document.getElementById("sm-refresh");
const smDelete = document.getElementById("sm-delete");
const smDeleteFiles = document.getElementById("sm-delete-files");
const smStatus = document.getElementById("sm-status");
const serverPills = document.getElementById("server-pills");

function setSmStatus(msg){
  if (smStatus) smStatus.textContent = msg || "";
}

function renderServerPillsInto(container){
  if (!container) return;
  container.innerHTML = "";
  serversCache.forEach(s => {
    const pillEl = document.createElement("a");
    pillEl.className = `server-pill ${s.running ? "running" : "stopped"} ${s.id === currentServerId ? "active" : ""}`;
    pillEl.href = `/servers/${encodeURIComponent(s.id)}`;
    const loc = String(s.location || (s.node_id ? "remote" : "local")).toLowerCase();
    const isRemote = (loc === "remote");
    const badgeText = isRemote ? "REMOTE" : "LOCAL";
    const badgeClass = isRemote ? "badge remote" : "badge local";
    const nodeHint = isRemote ? (s.node_label || s.node_name || s.node_id || "remote node") : "this node";
    pillEl.title = `${badgeText} • ${nodeHint}`;
    pillEl.innerHTML = `<span class="dot"></span><span class="txt">${escapeHtml(s.name)}</span><span class="${badgeClass}">${badgeText}</span>`;
    container.appendChild(pillEl);
  });
}

function renderAllServerPills(){
  // Sidebar selector
  if (serverSelector){
    renderServerPillsInto(serverSelector);
    if (serverSelectorHint){
      serverSelectorHint.textContent = serversCache.length
        ? "Choose a server to enter its URL-scoped controls."
        : "No servers yet. Create one in Server Management to begin.";
    }
  }

  // Server Management list
  renderServerPillsInto(serverPills);

  // NoBlackBox owns the only page-local server dropdown that follows this cache.
  if (document.getElementById("page-noblackbox")) {
    try{ window.__nobbSyncServerSelect && window.__nobbSyncServerSelect(); }catch{}
  }
}

async function loadServers(){
  setSmStatus("");
  let res, j;
  try{
    res = await fetch("/api/servers", { headers: {"Accept":"application/json"} });
    j = await res.json();
  }catch(e){
    console.warn("[servers] list:failed", e);
    // Keep the current cache if the response wasn't JSON (e.g. login redirect)
    renderAllServerPills();
    setPageStatus("The server list could not be refreshed. Retry this page.", "error");
    return;
  }

  if (!res.ok || !j || j.success === false){
    console.warn("[servers] list:bad_response", res?.status, j);
    renderAllServerPills();
    setPageStatus(`The server list could not be refreshed: ${j?.error || res?.status || "unknown error"}.`, "error");
    return;
  }

  serversCache = (j.servers || []);
  if (panelContext.scope === "server") {
    currentServerId = panelContext.serverId;
    if (!serversCache.find(s => String(s.id) === String(currentServerId))) {
      setPageStatus(`The URL target ${currentServerId} is no longer available. Return to Servers and choose another target.`, "error");
    }
  } else {
    currentServerId = null;
  }
  renderAllServerPills();
}


async function refreshServersSilent(){
  try{
    const res = await fetch("/api/servers");
    const j = await res.json();
    const incoming = (j.servers || []);
    serversCache = incoming;
    if (panelContext.scope === "server") {
      currentServerId = panelContext.serverId;
      if (!serversCache.find(s => String(s.id) === String(currentServerId))) {
        setPageStatus(`The URL target ${currentServerId} is no longer available. Return to Servers and choose another target.`, "error");
      }
    } else {
      currentServerId = null;
    }
    renderAllServerPills();
  }catch{
    // ignore transient errors
  }
}

async function refreshDeployNodeOptions(){
  if(!smNode) return;

  // Default: local-only
  const setLocalOnly = (note) => {
    smNode.innerHTML = "";
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "This node (local)";
    smNode.appendChild(opt);
    smNode.disabled = true;
    if(smNodeNote) smNodeNote.textContent = note || "Cluster disabled — deploying locally.";
  };

  try{
    const r = await apiFetch("/api/cluster/state");
    if(!r.ok || !r.data?.success){
      setLocalOnly("Cluster state unavailable — deploying locally.");
      return;
    }
    const c = r.data.cluster || {};
    if(!c.enabled){
      setLocalOnly("Cluster disabled — deploying locally.");
      return;
    }
    if(!c.is_coordinator){
      // members deploy on themselves only
      setLocalOnly("You are a cluster member — deploys happen on this node.");
      return;
    }

    // Coordinator: can choose any node
    smNode.disabled = false;
    smNode.innerHTML = "";

    const localOpt = document.createElement("option");
    localOpt.value = String(c.this_node?.node_id || "");
    localOpt.textContent = `This node (coordinator)`;
    smNode.appendChild(localOpt);

    const members = Array.isArray(c.members) ? c.members : [];
    for(const m of members){
      const opt = document.createElement("option");
      opt.value = String(m.node_id || "");
      const label = `${m.node_name || "Member"} (${m.ip || "?"}:${m.http_port || "?"})`;
      opt.textContent = label;
      smNode.appendChild(opt);
    }

    if(smNodeNote) smNodeNote.textContent = "Pick which node will host the server install.";
  }catch(e){
    setLocalOnly("Cluster state error — deploying locally.");
  }
}

async function createServerFromUI(){
  const name = smName?.value?.trim();
  const remote_commands_port = smRemotePort?.value ? parseInt(smRemotePort.value, 10) : 7779;
  const game_port = smGamePort?.value ? parseInt(smGamePort.value, 10) : null;
  const query_port = smQueryPort?.value ? parseInt(smQueryPort.value, 10) : null;
  const install_dir = smInstallDir?.value?.trim() || null;

  setSmStatus("Creating server (SteamCMD download/install may take a bit)…");
  const res = await fetch("/api/servers", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ name, remote_commands_port, game_port, query_port, install_dir, target_node_id: (smNode && !smNode.disabled ? (smNode.value || "") : "") })
  });
  const j = await res.json();
  if (!res.ok || !j.success){
    setSmStatus(`Create failed: ${j.error || res.statusText}`);
    if (j.stderr) console.error(j.stderr);
    return;
  }

  // Optimistic add: make sure the new server appears immediately even if the list endpoint
  // is briefly stale (or fails due to auth redirect / transient error).
  try{
    const created = j.server;
    if (created && created.id){
      const existing = serversCache.find(s => s.id === created.id);
      if (!existing){
        const targetNode = (smNode && !smNode.disabled) ? (smNode.value || "") : "";
        const inferredLocation = (targetNode && created.node_id && targetNode !== created.node_id) ? "remote" : "local";
        serversCache = [...serversCache, {
          id: created.id,
          name: created.name,
          install_dir: created.install_dir,
          remote_commands_port: created.remote_commands_port,
          running: false,
          node_id: created.node_id || targetNode || "",
          location: inferredLocation,
        }];
      }
    }
  }catch(e){
    console.warn("[servers] optimistic_add:failed", e);
  }

  // If backend provided an updated list (coordinator in cluster), prefer it.
  try{
    if (Array.isArray(j.servers)){
      serversCache = j.servers;
      renderAllServerPills();
    }
  }catch{}

  // Refresh pills/list (best-effort) so the authoritative view stays correct
  // (still do this even if j.servers was provided, in case cluster members changed)
  await loadServers();

  if (j.server?.id){
    setSelectedServer(j.server.id);
    renderAllServerPills();
  }

  // update status AFTER refresh so it doesn't look stuck on "creating..."
  setSmStatus(`Server installed successfully: ${j.server.name}`);

  // optional: clear the success message after a few seconds
  setTimeout(() => {
    const el = document.getElementById("sm-status");
    if (el && el.textContent?.includes("Server installed successfully")) el.textContent = "";
  }, 6000);

  // reload ports list so new remote port shows up
  await initPortsUI();

  // Extra safety: refresh again shortly after install to catch any delayed writes.
  setTimeout(() => { refreshServersSilent(); }, 1200);
}

async function deleteSelectedServer(){
  const s = getSelectedServer();
  if (!s){
    setSmStatus("No server selected.");
    return;
  }
  const deleteFiles = !!smDeleteFiles?.checked;
  if(!await confirmAction({
    title: deleteFiles ? "Delete server and files" : "Remove server from panel",
    message: deleteFiles
      ? `Permanently remove ${s.name} and its installation files from disk.`
      : `Remove ${s.name} from this panel. Existing installation files will remain on disk.`,
    confirmLabel: deleteFiles ? "Delete server and files" : "Remove server",
    tone: "danger",
    requireText: deleteFiles ? s.name : "",
  })) return;
  setSmStatus("Deleting server…");
  const res = await fetch(`/api/servers/${encodeURIComponent(s.id)}`, {
    method: "DELETE",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ delete_files: deleteFiles })
  });
  const j = await res.json();
  if (!res.ok || !j.success){
    setSmStatus(`Delete failed: ${j.error || res.statusText}`);
    return;
  }
  setSmStatus(`Deleted: ${j.removed?.name || s.name}`);
  currentServerId = null;
  window.location.assign(panelContext.serversPath || "/servers");
}

function wireServerManagementUI(){
  smCreate?.addEventListener("click", createServerFromUI);
  smRefresh?.addEventListener("click", loadServers);
  smDelete?.addEventListener("click", deleteSelectedServer);
}

async function initServersUI(){
  wireServerManagementUI();
  await refreshDeployNodeOptions();
  await loadServers();
}

// -----------------------------

// -----------------------------
// Workshop sync (Steam client cache -> panel missions folder)
// -----------------------------
function wireSyncWorkshopUI(){
  const btn = document.getElementById("sync-workshop-btn");
  const status = document.getElementById("sync-workshop-status");
  if(!btn) return;

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    if(status) status.textContent = "Syncing workshop missions...";
    pushResponse("Syncing Workshop missions from Steam cache...");
    try{
      if(!currentServerId){
      pushResponse("Select a server first.");
      if(status) status.textContent = "Select a server first.";
      btn.disabled = false;
      return;
    }
      const res = await fetch("/api/sync-workshop-missions", { method: "POST", headers: { "Content-Type":"application/json" }, body: JSON.stringify({ server_id: currentServerId }) });
      const j = await res.json();
      if(!j.success){
        const msg = j.error || "Sync failed";
        pushResponse("Workshop sync failed: " + msg);
        if(status) status.textContent = "Sync failed: " + msg;
      } else {
        pushResponse(`Workshop sync queued as job ${j.job.id}. It will continue if this page closes.`);
        if(status) status.textContent = `Queued. Track job ${j.job.id.slice(0,8)} on the Jobs page.`;
      }
    }catch(err){
      pushResponse("Workshop sync error: " + (err?.message || String(err)));
      if(status) status.textContent = "Sync error: " + (err?.message || String(err));
    }finally{
      btn.disabled = false;
    }
  });
}


// -----------------------------
// Cluster UI (admin)
// -----------------------------
function wireClusterUI(){
  if(!document.getElementById("page-cluster")) return;

  const createBtn = document.getElementById("cluster-create-btn");
  const refreshBtn = document.getElementById("cluster-refresh-btn");
  const joinBtn = document.getElementById("cluster-join-btn");
  const breakBtn = document.getElementById("cluster-break-btn");
  const leaveBtn = document.getElementById("cluster-leave-btn");
  const disbandBtn = document.getElementById("cluster-disband-btn");

  if(createBtn) createBtn.addEventListener("click", async () => {
    const name = (document.getElementById("cluster-create-name")?.value || "").trim();
    const broadcast = !!document.getElementById("cluster-create-broadcast")?.checked;
    console.log("[cluster] create:start", {name, broadcast});
    pushResponse(`Creating cluster${broadcast ? " (broadcast on LAN)" : ""}...`);
    const prevText = createBtn.textContent;
    createBtn.textContent = "Creating...";
    createBtn.classList.add("busy");
    createBtn.disabled = true;
    try{
      const r = await apiFetch("/api/cluster/create", {
        method: "POST",
        body: JSON.stringify({name, broadcast})
      });
      if(!r.ok || !r.data?.success) {
        pushResponse("Cluster create failed: " + (r.data?.error || r.statusText));
      } else {
        const secret = r.data?.cluster?.secret;
        const help = document.getElementById("cluster-create-secret");
        if(help) {
          help.innerHTML = secret ? `Join secret: <span class="mono">${escapeHtml(secret)}</span>` : "";
        }
        console.log("[cluster] create:ok", r.data);
        pushResponse("Cluster created.");
        await loadClusterPage(true);
      }
    }catch(err){
      pushResponse("Cluster create error: " + (err?.message || String(err)));
    }finally{
      createBtn.textContent = prevText;
      createBtn.classList.remove("busy");
      createBtn.disabled = false;
    }
  });

  if(refreshBtn) refreshBtn.addEventListener("click", async () => {
    console.log("[cluster] discovery:refresh");
    pushResponse("Looking for clusters on LAN...");
    const prevText = refreshBtn.textContent;
    refreshBtn.textContent = "Refreshing...";
    refreshBtn.classList.add("busy");
    refreshBtn.disabled = true;
    try{
      // Active probe makes discovery much more reliable.
      try{ await apiFetch("/api/cluster/discovery/probe", {method:"POST"}); }catch(e){}
      // Give the coordinator a brief moment to respond to the probe.
      await new Promise(r => setTimeout(r, 250));
      await loadClusterPage(false);
    }finally{
      refreshBtn.textContent = prevText;
      refreshBtn.classList.remove("busy");
      refreshBtn.disabled = false;
    }
  });

  if(joinBtn) joinBtn.addEventListener("click", async () => {
    const ip = (document.getElementById("cluster-join-ip")?.value || "").trim();
    const port = parseInt(document.getElementById("cluster-join-port")?.value || "5000", 10);
    const secret = (document.getElementById("cluster-join-secret")?.value || "").trim();

    // Immediate feedback so users know the click registered
    console.log("[cluster] join:start", {ip, port});
    pushResponse(`Joining cluster at ${ip || "(blank ip)"}:${port} ...`);

    const prevText = joinBtn.textContent;
    joinBtn.textContent = "Joining...";
    joinBtn.classList.add("busy");
    joinBtn.disabled = true;

    try{
      const r = await apiFetch("/api/cluster/join", {
        method: "POST",
        body: JSON.stringify({coordinator_ip: ip, coordinator_port: port, secret})
      });

      if(!r.ok || !r.data?.success) {
        console.warn("[cluster] join:failed", r);
        pushResponse("Join failed: " + (r.data?.error || r.statusText));
      } else {
        console.log("[cluster] join:ok", r.data);
        pushResponse("Joined cluster.");
        await loadClusterPage();
      }
    }catch(err){
      console.error("[cluster] join:error", err);
      pushResponse("Join error: " + (err?.message || String(err)));
    }finally{
      joinBtn.disabled = false;
      joinBtn.textContent = prevText;
      joinBtn.classList.remove("busy");
    }
  });


  if(breakBtn) breakBtn.addEventListener("click", async () => {
    if(!await confirmAction({
      title: "Break from cluster locally",
      message: "This failsafe removes local cluster state without notifying the coordinator.",
      confirmLabel: "Break locally",
      tone: "danger",
      requireText: "BREAK",
    })) return;
    breakBtn.disabled = true;
    try{
      const r = await apiFetch("/api/cluster/break", {method: "POST", body: JSON.stringify({})});
      if(!r.ok || !r.data?.success){
        pushResponse("Break failed: " + (r.data?.error || r.statusText));
      } else {
        pushResponse("Cluster broken locally.");
        await loadClusterPage();
      }
    }catch(err){
      pushResponse("Break error: " + (err?.message || String(err)));
    }finally{
      breakBtn.disabled = false;
    }
  });

  if(leaveBtn) leaveBtn.addEventListener("click", async () => {
    if(!await confirmAction({
      title: "Leave cluster",
      message: "The coordinator will remove this node from the cluster.",
      confirmLabel: "Leave cluster",
      tone: "danger",
    })) return;
    leaveBtn.disabled = true;
    try{
      const r = await apiFetch("/api/cluster/leave", { method: "POST" });
      if(!r.ok || !r.data?.success){
        pushResponse("Leave failed: " + (r.data?.error || r.statusText));
      } else {
        pushResponse("Left cluster.");
        await loadClusterPage();
      }
    }catch(err){
      pushResponse("Leave error: " + (err?.message || String(err)));
    }finally{
      leaveBtn.disabled = false;
    }
  });

  if(disbandBtn) disbandBtn.addEventListener("click", async () => {
    if(!await confirmAction({
      title: "Disband cluster",
      message: "This removes every member and permanently disbands the cluster.",
      confirmLabel: "Disband cluster",
      tone: "danger",
      requireText: "DISBAND",
    })) return;
    disbandBtn.disabled = true;
    try{
      const r = await apiFetch("/api/cluster/disband", { method: "POST" });
      if(!r.ok || !r.data?.success){
        pushResponse("Disband failed: " + (r.data?.error || r.statusText));
      } else {
        const fails = r.data?.failures || [];
        pushResponse("Cluster disbanded." + (fails.length ? (" Some members unreachable: " + fails.join(", ")) : ""));
        await loadClusterPage();
      }
    }catch(err){
      pushResponse("Disband error: " + (err?.message || String(err)));
    }finally{
      disbandBtn.disabled = false;
    }
  });

  // Coordinator convenience: auto-poll pending join requests so you don't have to spam Refresh.
  // This is lightweight (only hits /api/cluster/state and /api/cluster/join/requests).
  try{
    if(window.__CLUSTER_JOIN_POLL_TIMER__) clearInterval(window.__CLUSTER_JOIN_POLL_TIMER__);
  }catch(_){ }
  window.__CLUSTER_JOIN_POLL_TIMER__ = setInterval(async () => {
    try{
      const page = document.getElementById("page-cluster");
      if(!page || !page.classList.contains("show")) return;
      const st = await apiFetch("/api/cluster/state", { background: true });
      const isCoord = !!(st.ok && st.data?.success && st.data?.cluster?.is_coordinator);
      if(!isCoord) return;
      const wrap = document.getElementById("cluster-join-requests-wrap");
      const el = document.getElementById("cluster-join-requests");
      if(wrap) wrap.hidden = false;
      if(!el) return;

      const r = await apiFetch("/api/cluster/join/requests", { background: true });
      if(!r.ok || !r.data?.success) return;
      const reqs = r.data?.requests || [];

      // Notify when new requests appear
      const prevIds = new Set(window.__CLUSTER_REQ_IDS__ || []);
      const nextIds = new Set(reqs.map(x => x.request_id).filter(Boolean));
      for(const q of reqs){
        if(q?.request_id && !prevIds.has(q.request_id)){
          const n = q.node || {};
          const who = (n.node_name || n.node_id || "Member");
          pushResponse(`New cluster join request from ${who}. Approve it within 5 minutes.`);
        }
      }
      window.__CLUSTER_REQ_IDS__ = Array.from(nextIds);

      // If coordinator already has the list rendered by loadClusterPage, don't re-render constantly.
      // But if it's empty or showing "No pending requests" we can update.
      const needsRender = (el.innerHTML || "").includes("No pending requests") || (el.querySelectorAll("button[data-approve]").length !== reqs.length);
      if(!needsRender) return;

      if(reqs.length === 0){
        el.innerHTML = `<div class="item"><div><div class="t">No pending requests</div><div class="s">When a member clicks “Request join”, it will appear here.</div></div></div>`;
        return;
      }
      el.innerHTML = reqs.map(q => {
        const n = q.node || {};
        const name = n.node_name || n.node_id || "Member";
        const ip = n.ip || "";
        const port = n.http_port || "";
        return `<div class="item"><div><div class="t">${escapeHtml(name)}</div><div class="s mono">${escapeHtml(ip)}:${escapeHtml(String(port))}</div></div>
          <div class="actions"><button class="btn tiny primary" data-approve="1" data-rid="${escapeHtml(q.request_id||"")}">Approve</button></div>
        </div>`;
      }).join("");

      el.querySelectorAll("button[data-approve]").forEach(b => {
        // don't double-wire
        if(b.__wired) return;
        b.__wired = true;
        b.addEventListener("click", async () => {
          const rid = b.getAttribute("data-rid");
          if(!rid) return;
          b.disabled = true;
          const prev = b.textContent;
          b.textContent = "Approving...";
          try{
            const rr = await apiFetch("/api/cluster/join/approve", {method:"POST", body: JSON.stringify({request_id: rid})});
            if(!rr.ok || !rr.data?.success){
              const msg = (rr.data?.error || rr.data?.message || rr.error || (rr.status ? (`HTTP ${rr.status}`) : "unknown"));
              pushResponse("Approve failed: " + msg);
            } else {
              pushResponse("Approved. Member should appear as a cluster node.");
              await loadClusterPage(false);
            }
          }catch(err){
            pushResponse("Approve error: " + (err?.message || String(err)));
          }finally{
            b.disabled = false;
            b.textContent = prev;
          }
        });
      });
    }catch(_){ }
  }, 1200);
}


async function loadClusterPage(doProbe = true){
  if(!document.getElementById("page-cluster")) return;
  const status = document.getElementById("cluster-status");
  const discoveryList = document.getElementById("cluster-discovery-list");
  const secretEl = document.getElementById("cluster-create-secret");
  const membersEl = document.getElementById("cluster-members");

  // state
  try{
    const r = await apiFetch("/api/cluster/state");
    if(r.ok && r.data?.success){
      const c = r.data.cluster || {};
      if(status){
        status.hidden = false;
        if(!c.enabled){
          status.className = "notice";
          status.innerHTML = "Cluster: <b>disabled</b>";
        } else {
          status.className = c.is_coordinator ? "notice notice-good" : "notice";
          const role = c.is_coordinator ? "Coordinator" : "Member";
          const coord = c.coordinator ? `${c.coordinator.ip}:${c.coordinator.http_port}` : "(unknown)";
          status.innerHTML = `Cluster: <b>${escapeHtml(c.cluster_name||"")}</b> • ${role} • Coordinator: <span class="mono">${escapeHtml(coord)}</span>`;
        }
      }
      // keep deployment node dropdown in sync
      try{ await refreshDeployNodeOptions(); }catch(_){ }

      // show join secret (coordinator only)
      if(secretEl){
        if(c.enabled && c.is_coordinator && c.secret){
          secretEl.innerHTML = `Join secret: <span class="mono">${escapeHtml(String(c.secret))}</span>`;
        } else {
          secretEl.innerHTML = "";
        }
      }

      // enable/disable cluster actions based on state
      const createBtn = document.getElementById("cluster-create-btn");
      const joinBtn = document.getElementById("cluster-join-btn");
      const leaveBtn = document.getElementById("cluster-leave-btn");
      const disbandBtn = document.getElementById("cluster-disband-btn");
      const breakBtn = document.getElementById("cluster-break-btn");
      if(createBtn) createBtn.disabled = !!c.enabled;
      if(joinBtn) joinBtn.disabled = !!c.enabled;
      if(leaveBtn) leaveBtn.style.display = (c.enabled && !c.is_coordinator) ? "inline-flex" : "none";
      if(disbandBtn) disbandBtn.style.display = (c.enabled && c.is_coordinator) ? "inline-flex" : "none";
      if(breakBtn) breakBtn.disabled = !c.enabled;

      // remember local node identity for discovery self-join prevention
      window.__CLUSTER_LOCAL__ = {
        enabled: !!c.enabled,
        node_id: String((c.this_node||{}).node_id||""),
        ip: String((c.this_node||{}).ip||""),
        http_port: String((c.this_node||{}).http_port||""),
      };
      // members
      if(membersEl){
        const members = c.members || [];
        const mine = c.this_node || {};
        let html = "";
        html += `<div class="item"><div><div class="t">This node</div><div class="s mono">${escapeHtml(mine.node_name||"")} • ${escapeHtml(mine.ip||"")}:${escapeHtml(String(mine.http_port||""))}</div></div></div>`;
        if(members.length === 0){
          html += `<div class="item"><div><div class="t">No members yet</div><div class="s">Join this cluster from another machine’s Cluster Setup pill.</div></div></div>`;
        } else {
          for(const m of members){
            const last = m.last_seen ? new Date(m.last_seen*1000).toLocaleString() : "";
            html += `<div class="item"><div><div class="t">${escapeHtml(m.node_name||m.node_id||"")}</div><div class="s mono">${escapeHtml(m.ip||"")}:${escapeHtml(String(m.http_port||""))} • last seen ${escapeHtml(last)}</div></div></div>`;
          }
        }
        membersEl.innerHTML = html;
      }
    }
  }catch(_){ /* ignore */ }

  // discovery
  try{
    // Send an active probe first; coordinators respond immediately.
    if(doProbe){
      try{ await apiFetch("/api/cluster/discovery/probe", {method:"POST"}); }catch(e){}
      // small delay to allow probe responses to arrive
      await new Promise(r => setTimeout(r, 150));
    }
    const r2 = await apiFetch("/api/cluster/discovery");
    if(discoveryList){
      if(!r2.ok || !r2.data?.success){
        discoveryList.innerHTML = `<div class="item"><div><div class="t">Discovery unavailable</div><div class="s">${escapeHtml(r2.data?.error || r2.statusText)}</div></div></div>`;
      } else {
        const list = r2.data.clusters || [];
        if(list.length === 0){
          discoveryList.innerHTML = `<div class="item"><div><div class="t">No clusters found</div><div class="s">Make sure the coordinator has “Broadcast on LAN” enabled.</div></div></div>`;
        } else {
          const local = window.__CLUSTER_LOCAL__ || {};
          discoveryList.innerHTML = list.map(c => {
            const ip = c.coordinator_ip;
            const port = c.coordinator_port;
            const isSelf = (String(local.ip||"") === String(ip||"") && String(local.http_port||"") === String(port||""));
            const disabled = !!local.enabled || isSelf;
            const label = isSelf ? "This machine" : (local.enabled ? "In cluster" : "Request join");
            return `<div class="item"><div><div class="t">${escapeHtml(c.cluster_name||"")}</div><div class="s mono">${escapeHtml(ip)}:${escapeHtml(String(port))}</div></div>
              <div class="actions">
                <button class="btn tiny" data-cl-req="1" data-ip="${escapeHtml(ip)}" data-port="${escapeHtml(String(port))}" ${disabled ? "disabled" : ""}>${escapeHtml(label)}</button>
              </div>
            </div>`;
          }).join("");

          // wire "Request join" buttons
          discoveryList.querySelectorAll("button[data-cl-req]").forEach(btn => {
            btn.addEventListener("click", async () => {
              const ip = btn.getAttribute("data-ip") || "";
              const port = parseInt(btn.getAttribute("data-port") || "5000", 10);
              pushResponse(`Requesting to join ${ip}:${port} ...`);
              btn.disabled = true;
              const prev = btn.textContent;
              btn.textContent = "Requesting...";
              try{
                const r = await apiFetch("/api/cluster/join/request", {method:"POST", body: JSON.stringify({coordinator_ip: ip, coordinator_port: port})});
                if(!r.ok || !r.data?.success){
                  pushResponse("Join request failed: " + (r.data?.error || r.data?.message || ("HTTP " + r.status)));
                } else {
                  pushResponse("Join request sent. Waiting for coordinator approval (5 minutes).\nTip: ask the coordinator to open Cluster Setup and click Refresh until your request appears, then approve it." );
                }
              }catch(err){
                pushResponse("Join request error: " + (err?.message || String(err)));
              }finally{
                btn.disabled = false;
                btn.textContent = prev;
              }
            });
          });
        }
      }
    }
  }catch(_){ /* ignore */ }

  // coordinator: pending join requests
  try{
    const wrap = document.getElementById("cluster-join-requests-wrap");
    const el = document.getElementById("cluster-join-requests");
    const st = await apiFetch("/api/cluster/state");
    const isCoord = !!(st.ok && st.data?.success && st.data?.cluster?.is_coordinator);
    if(wrap) wrap.hidden = !isCoord;
    if(isCoord && el){
      const r = await apiFetch("/api/cluster/join/requests");
      if(!r.ok || !r.data?.success){
        el.innerHTML = `<div class="item"><div><div class="t">Unable to load requests</div><div class="s">${escapeHtml(r.data?.error || r.statusText)}</div></div></div>`;
      } else {
        const reqs = r.data?.requests || [];
        // notify coordinator if a new request appears
        try{
          const prevIds = new Set(window.__CLUSTER_REQ_IDS__ || []);
          const nextIds = new Set(reqs.map(x => x.request_id).filter(Boolean));
          for(const q of reqs){
            if(q?.request_id && !prevIds.has(q.request_id)){
              const n = q.node || {};
              const who = (n.node_name || n.node_id || "Member");
              pushResponse(`New cluster join request from ${who}. Open Cluster Setup and approve it within 5 minutes.`);
            }
          }
          window.__CLUSTER_REQ_IDS__ = Array.from(nextIds);
        }catch(_){ }
        if(reqs.length === 0){
          el.innerHTML = `<div class="item"><div><div class="t">No pending requests</div><div class="s">When a member clicks “Request join”, it will appear here.</div></div></div>`;
        } else {
          el.innerHTML = reqs.map(q => {
            const n = q.node || {};
            const name = n.node_name || n.node_id || "Member";
            const ip = n.ip || "";
            const port = n.http_port || "";
            return `<div class="item"><div><div class="t">${escapeHtml(name)}</div><div class="s mono">${escapeHtml(ip)}:${escapeHtml(String(port))}</div></div>
              <div class="actions"><button class="btn tiny primary" data-approve="1" data-rid="${escapeHtml(q.request_id||"")}">Approve</button></div>
            </div>`;
          }).join("");
          el.querySelectorAll("button[data-approve]").forEach(b => {
            b.addEventListener("click", async () => {
              const rid = b.getAttribute("data-rid");
              if(!rid) return;
              b.disabled = true;
              const prev = b.textContent;
              b.textContent = "Approving...";
              try{
                const r = await apiFetch("/api/cluster/join/approve", {method:"POST", body: JSON.stringify({request_id: rid})});
                if(!r.ok || !r.data?.success){
                  const msg = (r.data?.error || r.data?.message || r.error || (r.status ? (`HTTP ${r.status}`) : "unknown"));
                  pushResponse("Approve failed: " + msg);
                } else {
                  pushResponse("Approved. Member should appear as a cluster node.");
                  await loadClusterPage();
                }
              }catch(err){
                pushResponse("Approve error: " + (err?.message || String(err)));
              }finally{
                b.disabled = false;
                b.textContent = prev;
              }
            });
          });
        }
      }
    }
  }catch(_){ /* ignore */ }
}

// Coordinator helper: poll pending join requests so approvals show up without manual refresh.
async function pollClusterJoinRequests(){
  try{
    if(!document.getElementById("page-cluster")) return;
    // only poll while Cluster page is the active page
    const active = document.querySelector('.nav-item.active')?.getAttribute('data-page');
    if(active !== 'cluster') return;
    const st = await apiFetch("/api/cluster/state");
    const isCoord = !!(st.ok && st.data?.success && st.data?.cluster?.is_coordinator);
    if(!isCoord) return;
    // Update only the join requests section (fast)
    await loadClusterPage(false);
  }catch(_){ }
}

function wireDiscordUI(){
  const page = document.getElementById("page-discord");
  if(!page) return;
  if(page.dataset.wired === "1") return;
  page.dataset.wired = "1";

  const saveBtn = document.getElementById("discord-save");
  const startBtn = document.getElementById("discord-start");
  const stopBtn = document.getElementById("discord-stop");

  const tokenEl = document.getElementById("discord-token");
  const rolesEl = document.getElementById("discord-roles");
  const guildEl = document.getElementById("discord-guild");
  const channelEl = document.getElementById("discord-channel");
  const prefixEl = document.getElementById("discord-prefix");
  const panelUrlEl = document.getElementById("discord-panel-url");

  const statusEl = document.getElementById("discord-status");
  const indicatorDot = document.getElementById("discord-indicator-dot");
  const indicatorText = document.getElementById("discord-indicator-text");

  function setIndicator(state, text){
    if(indicatorDot){
      indicatorDot.classList.remove("running","stopped","error","unknown");
      indicatorDot.classList.add(state || "unknown");
    }
    if(indicatorText){
      indicatorText.textContent = text || (state ? state.toUpperCase() : "UNKNOWN");
    }
  }

  function setBusy(btn, busyText){
    if(!btn) return;
    if(!btn.__origText) btn.__origText = btn.textContent;
    if(busyText){
      btn.disabled = true;
      btn.classList.add("busy");
      btn.textContent = busyText;
    }else{
      btn.disabled = false;
      btn.classList.remove("busy");
      btn.textContent = btn.__origText;
    }
  }

  function bestMessage(resp, fallback){
    const d = resp?.data || {};
    return (
      d?.message ||
      d?.error ||
      d?.detail ||
      d?.data?.message ||
      d?.data?.error ||
      d?.status?.last_error ||
      d?.data?.status?.last_error ||
      fallback ||
      "unknown"
    );
  }

  async function refreshStatus(){
    try{
      const resp = await apiFetch("/api/discord/status");
      if(statusEl) statusEl.textContent = panelDiagnostics?.stringify(resp) || String(resp);

      const d = resp?.data || {};
      const st = d?.data?.status || d?.status || {};
      if(st?.running){
        setIndicator("running","RUNNING");
      }else if((st?.status || "").toLowerCase() === "error"){
        setIndicator("error","ERROR");
      }else if((st?.status || "").toLowerCase() === "stopped" || st?.running === false){
        setIndicator("stopped","STOPPED");
      }else{
        setIndicator("unknown","UNKNOWN");
      }
    }catch(e){
      if(statusEl) statusEl.textContent = "Failed to load status: " + e;
      setIndicator("unknown","UNKNOWN");
    }
  }

  // Alias for older callers + expose for navigation
  const refreshDiscordStatus = refreshStatus;
  window.refreshDiscordStatus = refreshStatus;


  if(saveBtn && !saveBtn.__wired){
    saveBtn.__wired = true;
    saveBtn.addEventListener("click", async (ev) => {
      try{
        ev.preventDefault();
        console.log("[discord] save:start");
        setBusy(saveBtn, "Saving...");
        setResponse("Saving Discord bot config...");

        const payload = {
          token: (tokenEl?.value || "").trim(),
          allowed_role_ids: (rolesEl?.value || "").trim(),
          guild_id: (guildEl?.value || "").trim(),
          channel_id: (channelEl?.value || "").trim(),
          command_prefix: (prefixEl?.value || "!").trim() || "!",
          panel_base_url: (panelUrlEl?.value || "http://127.0.0.1:5000").trim(),
          enabled: true
        };
        if(!payload.token) delete payload.token;

        const resp = await apiFetch("/api/discord/config", {method:"POST", body: JSON.stringify(payload)});
        console.log("[discord] save:resp", resp);

        if(resp?.ok){
          setResponse("Saved Discord bot config.");
        }else{
          const msg = bestMessage(resp, "save failed");
          setResponse(`Save failed (${resp?.status}): ${msg}`);
        }
        await refreshStatus();
      }catch(e){
        console.error("[discord] save:error", e);
        setResponse("Save failed: " + (e?.message || e));
      }finally{
        setBusy(saveBtn, null);
      }
    });
  }

  if(startBtn && !startBtn.__wired){
    startBtn.__wired = true;
    startBtn.addEventListener("click", async (ev) => {
      try{
        ev.preventDefault();
        console.log("[discord] start:start");
        setBusy(startBtn, "Starting...");
        setResponse("Starting Discord bot...");

        const resp = await apiFetch("/api/discord/start", {method:"POST"});
        console.log("[discord] start:resp", resp);

        if(resp?.ok){
          setResponse(resp?.data?.message || "Discord bot start requested.");
        }else{
          const msg = bestMessage(resp, "start failed");
          setResponse(`Start failed (${resp?.status}): ${msg}`);
        }
        await refreshStatus();
      }catch(e){
        console.error("[discord] start:error", e);
        setResponse("Start failed: " + (e?.message || e));
      }finally{
        setBusy(startBtn, null);
      }
    });
  }

  if(stopBtn && !stopBtn.__wired){
    stopBtn.__wired = true;
    stopBtn.addEventListener("click", async (ev) => {
      try{
        ev.preventDefault();
        if(!await confirmAction({
          title: "Stop Discord bot",
          message: "Panel commands through Discord will be unavailable until the bot starts again.",
          confirmLabel: "Stop bot",
          tone: "danger",
        })) return;
        console.log("[discord] stop:start");
        setBusy(stopBtn, "Stopping...");
        setResponse("Stopping Discord bot...");

        const resp = await apiFetch("/api/discord/stop", {method:"POST"});
        console.log("[discord] stop:resp", resp);

        if(resp?.ok){
          setResponse(resp?.data?.message || "Discord bot stop requested.");
        }else{
          const msg = bestMessage(resp, "stop failed");
          setResponse(`Stop failed (${resp?.status}): ${msg}`);
        }
        await refreshStatus();
      }catch(e){
        console.error("[discord] stop:error", e);
        setResponse("Stop failed: " + (e?.message || e));
      }finally{
        setBusy(stopBtn, null);
      }
    });
  }

  window.__discordRefreshStatus = refreshStatus;


  // initial load
  refreshStatus().catch(()=>{});
}


// Boot
// -----------------------------
document.addEventListener("DOMContentLoaded", async () => {
  initializePage(panelContext.activePage || "dashboard");

  // Load current user/role first so we can gate UI + API behavior
  let role = "moderator";
  try {
    const me = await apiFetch("/api/whoami");
    if (me.ok && me.data?.success) {
      const el = document.getElementById("current-user");
      if (el) el.textContent = `${me.data.username || ""} (${me.data.role || ""})`;
      role = (me.data.role || "moderator").toLowerCase();
      window.__USER_ROLE__ = role;
    }
  } catch (e) {
    // if whoami fails, the global apiFetch 401 handler will bounce to login
  }

  // Moderator restrictions (UI only; backend enforces too)
  if (role !== "admin") {
    document.querySelectorAll("[data-admin-only]").forEach((element) => {
      element.toggleAttribute("hidden", true);
    });

    // Hide admin-only dashboard controls
    const reloadForm = document.getElementById("reload-config-form");
    if (reloadForm) reloadForm.style.display = "none";

    const updateBtn = document.getElementById("update-server-btn");
    if (updateBtn) updateBtn.style.display = "none";

    const syncBtn = document.getElementById("sync-workshop-btn");
    if (syncBtn) syncBtn.style.display = "none";
  }

  // Branding
  try { bindBrandingUI(); } catch (_) {}
  try { await loadBranding(); } catch (_) {}

  // Init shared pages
  await initServersUI();

  // Admin-only init
  if (role === "admin") {
    // init ports first so dropdown is consistent
    await initPortsUI();
    await initServerAccessUI();
    await initServerSettingsUI();
    wireSyncWorkshopUI();
    wireClusterUI();
  }

  // Discord bot UI should still wire even if role detection is off;
  // server-side will enforce permissions.
  wireDiscordUI();

  // Keep power indicators/pills fresh
  setInterval(refreshServersSilent, 3000);
});

// =============================
// NOBlackBox page
// =============================
(function(){
  const ids = (k) => document.getElementById(k);
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const el = {
    serverSelect: ids("nobb-server-select"),
    statusPill: ids("nobb-status-pill"),
    paths: ids("nobb-paths"),
    installBtn: ids("nobb-install-btn"),
    uninstallBtn: ids("nobb-uninstall-btn"),
    pickBtn: ids("nobb-pick-folder-btn"),
    applyPathBtn: ids("nobb-apply-path-btn"),
    saveBtn: ids("nobb-save-btn"),
    reloadBtn: ids("nobb-reload-btn"),
    progress: ids("nobb-progress"),
    outputPath: ids("nobb-outputpath"),

    unitDiscovery: ids("nobb-unit-discovery"),
    bulletsimDiscovery: ids("nobb-bulletsim-discovery"),
    shockwaveDiscovery: ids("nobb-shockwave-discovery"),
    aircraftUpdate: ids("nobb-aircraft-update"),
    vehicleUpdate: ids("nobb-vehicle-update"),
    munitionUpdate: ids("nobb-munition-update"),
    shockwaveUpdate: ids("nobb-shockwave-update"),
    tracerUpdate: ids("nobb-tracer-update"),
    flareUpdate: ids("nobb-flare-update"),
    buildingUpdate: ids("nobb-building-update"),

    autosave: ids("nobb-autosave"),
    autostart: ids("nobb-autostart"),
    recordEjected: ids("nobb-record-ejected"),
    destruction: ids("nobb-destruction"),

    useMissionTime: ids("nobb-use-mission-time"),
    recordSteamID: ids("nobb-record-steamid"),
    recordSpeed: ids("nobb-record-speed"),
    recordAOA: ids("nobb-record-aoa"),
    recordAGL: ids("nobb-record-agl"),
    recordRadar: ids("nobb-record-radar"),
    recordGear: ids("nobb-record-gear"),
    recordHead: ids("nobb-record-head"),
    recordExtra: ids("nobb-record-extra"),
    compressIDs: ids("nobb-compress-ids"),

    heightmapEnable: ids("nobb-heightmap-enable"),
    metersPerScan: ids("nobb-meters-per-scan"),
    heightmapRes: ids("nobb-heightmap-res"),
  };

  function toBool(v, def=false){
    if (v === undefined || v === null) return def;
    const s = String(v).trim().toLowerCase();
    if (["true","1","yes","on"].includes(s)) return true;
    if (["false","0","no","off"].includes(s)) return false;
    return def;
  }

  function setStatus(text, kind=""){
    if (!el.statusPill) return;
    el.statusPill.textContent = text;
    el.statusPill.classList.remove("good","warn","bad");
    if (kind) el.statusPill.classList.add(kind);
  }

  function syncServerSelect(){
    if (!el.serverSelect) return;
    const prev = el.serverSelect.value || "";
    el.serverSelect.innerHTML = "";

    if (!serversCache.length){
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "No servers";
      el.serverSelect.appendChild(opt);
      el.serverSelect.disabled = true;
      return;
    }

    el.serverSelect.disabled = false;
    for (const s of serversCache){
      const opt = document.createElement("option");
      opt.value = String(s.id || "");
      opt.textContent = String(s.name || s.id || "(server)");
      el.serverSelect.appendChild(opt);
    }

    // Keep selection stable
    const desired = currentServerId || prev || (serversCache[0] && serversCache[0].id) || "";
    if (desired) el.serverSelect.value = desired;
  }

  // expose so the main server selector refresh can update our dropdown
  window.__nobbSyncServerSelect = syncServerSelect;

  async function load(){
    const sid = currentServerId || "";
    if (!sid){
      clearProgress();
      setProgress(["Select a server to configure NOBlackBox."]);
      return;
    }

    // Optional status probe (no UI pill; we only use the progress log)
    const st = await apiFetch(`/api/noblackbox/status?server_id=${encodeURIComponent(sid)}`, { method:"GET" });
    if (st?.ok && st.data?.success){
      const modTxt = st.data.installed ? "Installed" : "Missing";
      const cfgTxt = st.data.has_config ? "present" : (isSelectedServerRemote() ? "unknown (remote)" : "missing");
      appendProgress(`Status: Mod ${modTxt} (config ${cfgTxt})`);
      // Extra debug for troubleshooting path/detection issues
      // (Debug output removed)
    } else {
      // Don't block config loading if status fails
      appendProgress(`Status: (unavailable)${st?.status ? " HTTP "+st.status : ""}`);
    }

    const cfg = await apiFetch(`/api/noblackbox/config?server_id=${encodeURIComponent(sid)}`, { method:"GET" });
    if (!(cfg?.ok && cfg.data?.success)){
      const err = cfg?.data?.error || (cfg?.ok ? "" : `HTTP ${cfg?.status || ""}`);
      appendProgress(err ? ("❌ " + err) : "ℹ️ Config not found yet. Install NOBlackBox to generate it.");
      return;
    }
    const c = cfg.data.config || {};
          if (el.outputPath) el.outputPath.value = c["OutputPath"] || "";

          if (el.unitDiscovery) el.unitDiscovery.value = c["Unit Discovery Rate"] || "1";
          if (el.bulletsimDiscovery) el.bulletsimDiscovery.value = c["BulletSim Discovery Rate"] || "0.2";
          if (el.shockwaveDiscovery) el.shockwaveDiscovery.value = c["Shockwave Discovery Rate"] || "0.5";
          if (el.aircraftUpdate) el.aircraftUpdate.value = c["Aircraft Update Rate"] || "0.2";
          if (el.vehicleUpdate) el.vehicleUpdate.value = c["Vehicle Update Rate"] || "1";
          if (el.munitionUpdate) el.munitionUpdate.value = c["Munition Update Rate"] || "0.2";
          if (el.shockwaveUpdate) el.shockwaveUpdate.value = c["Shockwave Update Rate"] || "0.016";
          if (el.tracerUpdate) el.tracerUpdate.value = c["Tracer Update Rate"] || "0.2";
          if (el.flareUpdate) el.flareUpdate.value = c["Flare Update Rate"] || "1";
          if (el.buildingUpdate) el.buildingUpdate.value = c["Building Update Rate"] || "1";

          if (el.autosave) el.autosave.value = c["AutoSaveInterval"] || "60";
          if (el.autostart) el.autostart.checked = toBool(c["AutoStartRecording"], true);
          if (el.recordEjected) el.recordEjected.checked = toBool(c["RecordEjectedPilots"], false);
          if (el.destruction) el.destruction.checked = toBool(c["DestructionEvents"], true);

          if (el.useMissionTime) el.useMissionTime.checked = toBool(c["UseMissionTime"], true);
          if (el.recordSteamID) el.recordSteamID.checked = toBool(c["RecordSteamID"], true);
          if (el.recordSpeed) el.recordSpeed.checked = toBool(c["RecordSpeed"], true);
          if (el.recordAOA) el.recordAOA.checked = toBool(c["RecordAOA"], true);
          if (el.recordAGL) el.recordAGL.checked = toBool(c["RecordAGL"], true);
          if (el.recordRadar) el.recordRadar.checked = toBool(c["RecordRadarMode"], true);
          if (el.recordGear) el.recordGear.checked = toBool(c["RecordLandingGear"], true);
          if (el.recordHead) el.recordHead.checked = toBool(c["RecordPilotHead"], true);
          if (el.recordExtra) el.recordExtra.checked = toBool(c["RecordExtraTelemetry"], true);
          if (el.compressIDs) el.compressIDs.checked = toBool(c["CompressIDs"], false);

          if (el.heightmapEnable) el.heightmapEnable.checked = toBool(c["EnableHeightmapGenerator"], false);
          if (el.metersPerScan) el.metersPerScan.value = c["MetersPerScan"] || "4";
          if (el.heightmapRes) el.heightmapRes.value = c["HeightMapResolution"] || "4096";
  }

  async function save(values){
    const sid = currentServerId || "";
    if (!sid) return false;
    const resp = await apiFetch("/api/noblackbox/config", {
      method: "POST",
      body: JSON.stringify({ server_id: sid, values }),
    });
    // apiFetch returns { ok, status, data }
    if (!(resp?.ok && resp.data?.success)){
      const err = resp?.data?.error || (resp?.ok ? "unknown error" : `HTTP ${resp?.status || ""}`);
      appendProgress(`❌ Save failed: ${err}`);
      return false;
    }
    appendProgress(`✅ Settings saved as v${resp.data.config_version?.version?.version_number || "?"}.`);
    return true;
  }


  function clearProgress(){
    if (el.progress) el.progress.textContent = "";
  }
  function setProgress(lines){
    if (!el.progress) return;
    el.progress.textContent = (lines || []).join("\n");
  }
  function appendProgress(line){
    if (!el.progress) return;
    const cur = (el.progress.textContent || "").trimEnd();
    el.progress.textContent = (cur ? (cur + "\n") : "") + String(line);
  }
  async function pollJob(sid){
    const j = await apiFetch(`/api/noblackbox/job?server_id=${encodeURIComponent(sid)}`, { background: true, method:"GET" });
    if (j?.ok && j.data?.success){
      setProgress(j.data.lines || []);
      if (j.data.done){
        appendProgress(j.data.ok ? "✅ Install finished." : `❌ Install failed: ${j.data.error || "unknown error"}`);
        await appendStatusAfterJob(sid);
        return false;
      }

  async function appendStatusAfterJob(sid){
    const st = await apiFetch(`/api/noblackbox/status?server_id=${encodeURIComponent(sid)}`, { background: true, method:"GET" });
    if (st?.ok && st.data?.success){
      // backend uses `installed` for the mod/plugin presence
      const modTxt = st.data.installed ? "Installed" : "Missing";
      const cfgTxt = st.data.has_config ? "present" : "missing";
      appendProgress(`Status: Mod ${modTxt} (config ${cfgTxt})`);
    } else {
      appendProgress(`Status: (unavailable)${st?.status ? " HTTP "+st.status : ""}`);
    }
  }

  async function waitForInstallByStatus(sid, timeoutMs=10*60*1000){
    // Fallback: sometimes the in-memory job log can fail to report completion.
    // Status probing is cheap and reliable because it checks real files.
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline){
      const st = await apiFetch(`/api/noblackbox/status?server_id=${encodeURIComponent(sid)}`, { background: true, method:"GET" });
      if (st?.ok && st.data?.success){
        if (st.data.installed){
          appendProgress("✅ Install complete.");
          const cfgTxt = st.data.has_config ? "present" : "missing";
          appendProgress(`Status: Mod Installed (config ${cfgTxt})`);
          return true;
        }
      }
      await sleep(1500);
    }
    return false;
  }

      return true;
    }
    // show minimal transport-level debug
    if (!j?.ok){
      appendProgress(`Job poll failed (HTTP ${j?.status || ""})`);
    }
    return false;
  }
  async function pollJobUntilDone(sid){
    // Poll up to ~10 minutes. Important: the backend may take a moment to create the job,
    // so don't stop immediately on a "no job" response right after clicking Install.
    const deadline = Date.now() + (10*60*1000);
    let sawRunning = false;
    let lastStatusProbe = 0;
    while (Date.now() < deadline){
      const cont = await pollJob(sid); // true = keep polling, false = done OR no-job/error
      if (cont){
        sawRunning = true;
        // Even if the in-memory job log doesn't update (rare), the real on-disk status will.
        // Probe status periodically so the user gets an "install complete" message without needing Reload.
        if (Date.now() - lastStatusProbe > 2500){
          lastStatusProbe = Date.now();
          try{
            const st = await apiFetch(`/api/noblackbox/status?server_id=${encodeURIComponent(sid)}`, { background: true, method:"GET" });
            if (st?.ok && st.data?.success && st.data.installed){
              appendProgress("✅ Install complete.");
              const cfgTxt = st.data.has_config ? "present" : "missing";
              appendProgress(`Status: Mod Installed (config ${cfgTxt})`);
              return { completed: true };
            }
          }catch(_){ }
        }
        await sleep(1000);
        continue;
      }

      // If we already saw the job running, pollJob() has printed the final status (done/failed).
      if (sawRunning) return { completed: true };

      // Grace period: job not visible yet; keep polling.
      await sleep(1000);
    }
    // If the job mechanism never reported completion, fall back to probing real status.
    const ok = await waitForInstallByStatus(sid, 2*60*1000);
    return { completed: ok };
  }

  function bindOnce(){
    if (window.__nobbBound) return;
    window.__nobbBound = true;

    // populate and wire server dropdown
    syncServerSelect();
    if (el.serverSelect){
      el.serverSelect.addEventListener("change", async () => {
        const id = el.serverSelect.value || "";
        if (id) setSelectedServer(id);
        await load();
      });
    }

    if (el.reloadBtn) el.reloadBtn.addEventListener("click", load);

    if (el.installBtn) el.installBtn.addEventListener("click", async () => {
      const sid = currentServerId || "";
      if (!sid) return;
      if (!await confirmAction({
        title: "Install NoBlackBox",
        message: "Install BepInEx and the public-source NoBlackBox plugin into the selected server?",
        confirmLabel: "Install NoBlackBox",
      })) return;
      clearProgress();
      setProgress(["Starting NOBlackBox install..."]);
      const r = await apiFetch("/api/noblackbox/install", {
        method: "POST",
        body: JSON.stringify({ server_id: sid }),
      });
      if (!(r?.ok && r.data?.success)){
        const err = r?.data?.error || (r?.ok ? "unknown error" : `HTTP ${r?.status || ""}`);
        appendProgress(`❌ Install request failed: ${err}`);
        notify(err || "Install failed", "error");
        return;
      }
      const jobId = String(r.data.job?.id || "");
      appendProgress(`Install queued as job ${jobId}.`);
      appendProgress("It will continue if this page closes. Track durable progress on the server Jobs page.");
});

    if (el.uninstallBtn) el.uninstallBtn.addEventListener("click", async () => {
      const sid = currentServerId || "";
      if (!sid) return;
      if (!await confirmAction({
        title: "Uninstall NoBlackBox",
        message: "Remove the NoBlackBox plugin files from the selected server? Existing recordings are not removed.",
        confirmLabel: "Uninstall NoBlackBox",
        tone: "danger",
        requireText: "UNINSTALL",
      })) return;
      const r = await apiFetch("/api/noblackbox/uninstall", {
        method: "POST",
        body: JSON.stringify({ server_id: sid }),
      });
      if (!(r?.ok && r.data?.success)){
        const err = r?.data?.error || (r?.ok ? "unknown error" : `HTTP ${r?.status || ""}`);
        appendProgress(`❌ Uninstall failed: ${err}`);
        notify(err || "Uninstall failed", "error");
        return;
      }
      appendProgress("🗑️ NOBlackBox uninstalled.");
      await load();
    });

    if (el.pickBtn) el.pickBtn.addEventListener("click", async () => {
      appendProgress("📁 Picking recording path...");
      const r = await apiFetch("/api/noblackbox/pick-folder", { method:"POST", body:"{}" });
      if (!(r?.ok && r.data?.success)){
        const err = r?.data?.error || (r?.ok ? "unknown error" : `HTTP ${r?.status || ""}`);
        appendProgress("❌ Pick path failed: " + err);
        notify(err || "Pick folder failed", "error");
        return;
      }
      if (el.outputPath) el.outputPath.value = r.data.path || "";
      appendProgress("✅ Selected: " + (r.data.path || ""));
      notify("Path selected", "success");
    });

    if (el.applyPathBtn) el.applyPathBtn.addEventListener("click", async () => {
      // Save the custom recording path and show a clear confirmation in the console.
      const ok = await save({ "OutputPath": el.outputPath?.value || "" });
      if (ok) appendProgress("✅ Custom path loaded, ready to install.");
      await load();
    });

    if (el.saveBtn) el.saveBtn.addEventListener("click", async () => {
      const values = {
        "OutputPath": el.outputPath?.value || "",
        "Unit Discovery Rate": el.unitDiscovery?.value || "1",
        "BulletSim Discovery Rate": el.bulletsimDiscovery?.value || "0.2",
        "Shockwave Discovery Rate": el.shockwaveDiscovery?.value || "0.5",
        "Aircraft Update Rate": el.aircraftUpdate?.value || "0.2",
        "Vehicle Update Rate": el.vehicleUpdate?.value || "1",
        "Munition Update Rate": el.munitionUpdate?.value || "0.2",
        "Shockwave Update Rate": el.shockwaveUpdate?.value || "0.016",
        "Tracer Update Rate": el.tracerUpdate?.value || "0.2",
        "Flare Update Rate": el.flareUpdate?.value || "1",
        "Building Update Rate": el.buildingUpdate?.value || "1",
        "AutoSaveInterval": el.autosave?.value || "60",
        "AutoStartRecording": !!el.autostart?.checked,
        "RecordEjectedPilots": !!el.recordEjected?.checked,
        "DestructionEvents": !!el.destruction?.checked,
        "UseMissionTime": !!el.useMissionTime?.checked,
        "RecordSteamID": !!el.recordSteamID?.checked,
        "RecordSpeed": !!el.recordSpeed?.checked,
        "RecordAOA": !!el.recordAOA?.checked,
        "RecordAGL": !!el.recordAGL?.checked,
        "RecordRadarMode": !!el.recordRadar?.checked,
        "RecordLandingGear": !!el.recordGear?.checked,
        "RecordPilotHead": !!el.recordHead?.checked,
        "RecordExtraTelemetry": !!el.recordExtra?.checked,
        "CompressIDs": !!el.compressIDs?.checked,
        "EnableHeightmapGenerator": !!el.heightmapEnable?.checked,
        "MetersPerScan": el.metersPerScan?.value || "4",
        "HeightMapResolution": el.heightmapRes?.value || "4096",
      };
      await save(values);
      await load();
    });
  }

  window.loadNoBlackBox = async function(){
    // Force the main scroll container to the top when opening this page.
    // NOBlackBox has a compact card; if the scroll position is preserved from another page,
    // it can look like the whole page is "stuck" at the bottom.
    try {
      const leftCol = document.querySelector('.col');
      if (leftCol) {
        leftCol.scrollTop = 0;
        requestAnimationFrame(() => { try { leftCol.scrollTop = 0; } catch {} });
      }
    } catch (_) {}
    bindOnce();
    await load();
  };
})();

// -----------------------------
// Moderation
// -----------------------------
let moderationState = { tickets: [], closed_tickets: [], settings: {} };
let moderationSelectedSteamId = null;
let moderationInstallPoll = null;
let moderationFormDirty = false;

function moderationSetInstallLines(lines){
  const wrap = document.getElementById('mod-install-progress');
  if (!wrap) return;
  const arr = Array.isArray(lines) ? lines : [];
  wrap.innerHTML = arr.length ? arr.map(x => `<div class="list-item"><div>${escapeHtml(String(x||''))}</div></div>`).join('') : '<div class="muted small">Install output will appear here.</div>';
}

function moderationSetInstallStatus(text){
  const el = document.getElementById('mod-install-status');
  if (el) el.textContent = text || '';
}

function moderationSetProgress(job){
  const wrap = document.getElementById('mod-install-progress-meter');
  const progress = wrap?.querySelector('progress');
  const value = wrap?.querySelector('.progress-block > div > span:last-child');
  if (!wrap || !progress || !job) return;
  const total = Math.max(1, Number(job.progress_total || 1));
  const percent = Math.min(100, Math.round((Number(job.progress_current || 0) / total) * 100));
  wrap.hidden = false;
  progress.value = percent;
  if (value) value.textContent = `${percent}%`;
}

async function moderationRefreshStatus(){
  if (!currentServerId) return null;
  const res = await apiFetch(`/api/moderation/status?server_id=${encodeURIComponent(currentServerId)}`, { method:'GET' });
  if (!res.ok || !res.data?.success){
    moderationSetInstallStatus(res.data?.error || 'Failed to load moderation status.');
    return null;
  }
  const st = res.data;
  moderationSetInstallStatus(st.installed ? 'Moderation module installed' : 'Moderation module not installed');
  const state = document.getElementById('mod-install-state');
  if (state) {
    state.className = `status-badge status-badge--${st.installed ? 'success' : 'warning'}`;
    state.innerHTML = `<span class="status-dot" aria-hidden="true"></span>${st.installed ? 'Installed' : 'Action needed'}`;
  }
  const paths = document.getElementById('mod-install-paths');
  if (paths) paths.textContent = `Plugin: ${st.plugin_path || 'not found'} · Config: ${st.cfg_path || 'not found'} · State: ${st.state_path || 'not found'}`;
  return st;
}

async function moderationPollInstallJob(){
  if (!currentServerId) return;
  const res = await apiFetch(`/api/moderation/job?server_id=${encodeURIComponent(currentServerId)}`, { background: true, method:'GET' });
  if (!res.ok || !res.data?.success) return;
  moderationSetInstallLines(res.data.lines || []);
  moderationSetProgress(res.data.job);
  if (res.data.done){
    if (moderationInstallPoll){ clearInterval(moderationInstallPoll); moderationInstallPoll = null; }
    await moderationRefreshStatus();
    await window.loadModerationPage();
    if (!res.data.ok) notify(res.data.error || 'Moderation mod install failed.', 'error');
  }
}

function moderationTicketSteamId(t){ return String(t?.OffenderSteamId ?? t?.offenderSteamId ?? ''); }
function moderationTicketStatus(t){ return String(t?.Status ?? t?.status ?? 'open').toLowerCase(); }
function moderationTicketClaimedBy(t){ return String(t?.ClaimedBy ?? t?.claimedBy ?? ''); }
function moderationTicketName(t){ return String(t?.OffenderName ?? t?.offenderName ?? moderationTicketSteamId(t) ?? 'Unknown'); }
function moderationTicketIncidents(t){ return Array.isArray(t?.Incidents) ? t.Incidents : (Array.isArray(t?.incidents) ? t.incidents : []); }
function moderationTicketComments(t){ return Array.isArray(t?.Comments) ? t.Comments : (Array.isArray(t?.comments) ? t.comments : []); }

function renderModerationLists(){
  const openWrap = document.getElementById('mod-open-tickets');
  const closedWrap = document.getElementById('mod-closed-tickets');
  const renderOne = (t) => {
    const sid = moderationTicketSteamId(t);
    const active = sid === moderationSelectedSteamId ? " is-selected" : "";
    const counts = `A:${Number(t?.AircraftCount ?? 0)} V:${Number(t?.VehicleCount ?? 0)} S:${Number(t?.ShipCount ?? 0)}`;
    const claimed = moderationTicketClaimedBy(t) || 'none';
    return `<button class="pill${active}" data-mod-ticket="${escapeAttr(sid)}"><b>${escapeHtml(moderationTicketName(t))}</b> • ${escapeHtml(sid)} • ${escapeHtml(counts)} • claimed by ${escapeHtml(claimed)}</button>`;
  };
  renderList(openWrap, (moderationState.tickets||[]).length ? moderationState.tickets.map(renderOne).join(' ') : '<div class="muted small">No open tickets.</div>');
  renderList(closedWrap, (moderationState.closed_tickets||[]).length ? moderationState.closed_tickets.map(renderOne).join(' ') : '<div class="muted small">No closed tickets.</div>');
  document.querySelectorAll('[data-mod-ticket]').forEach(btn => btn.onclick = () => { moderationSelectedSteamId = btn.dataset.modTicket; renderModerationDetail(); renderModerationLists(); });
}

function renderModerationDetail(){
  const wrap = document.getElementById('mod-ticket-detail');
  const all = [...(moderationState.tickets||[]), ...(moderationState.closed_tickets||[])];
  const t = all.find(x => moderationTicketSteamId(x) === moderationSelectedSteamId);
  if (!wrap) return;
  if (!t){ wrap.innerHTML = '<div class="muted small">Select a ticket.</div>'; return; }
  const incidents = moderationTicketIncidents(t).slice().sort((a,b)=> String(b?.TimestampUtc||b?.timestampUtc||'').localeCompare(String(a?.TimestampUtc||a?.timestampUtc||'')));
  const comments = moderationTicketComments(t).slice().sort((a,b)=> String(a?.TimestampUtc||a?.timestampUtc||'').localeCompare(String(b?.TimestampUtc||b?.timestampUtc||'')));
  const isClosed = moderationTicketStatus(t) === 'closed';
  wrap.innerHTML = `
    <div class="field"><label>Offender</label><div>${escapeHtml(moderationTicketName(t))} (${escapeHtml(moderationTicketSteamId(t))})</div></div>
    <div class="field"><label>Status</label><div>${escapeHtml(moderationTicketStatus(t))} • claimed by ${escapeHtml(moderationTicketClaimedBy(t) || 'none')}</div></div>
    <div class="btns">
      <button class="btn ghost" data-mod-action="claim">Claim</button>
      <button class="btn ghost" data-mod-action="unclaim">Unclaim</button>
      <button class="btn ${isClosed ? 'good' : 'warn'}" data-mod-action="${isClosed ? 'reopen' : 'close'}">${isClosed ? 'Reopen' : 'Close'}</button>
      <button class="btn danger" data-mod-action="kick">Kick</button>
      <button class="btn danger" data-mod-action="ban">Ban</button>
    </div>
    <div class="field"><label>Add comment</label><div class="row"><input id="mod-comment-text" class="grow" placeholder="Comment for other moderators" /><button class="btn primary" id="mod-comment-btn" type="button">Post</button></div></div>
    <div class="field"><label>Incidents</label><div class="list">${incidents.length ? incidents.map(i => `<div class="list-item"><div><b>${escapeHtml(String(i?.Summary ?? i?.summary ?? ''))}</b></div><div class="muted small">${escapeHtml(String(i?.TimestampUtc ?? i?.timestampUtc ?? ''))}</div></div>`).join('') : '<div class="muted small">No incidents.</div>'}</div></div>
    <div class="field"><label>Comments</label><div class="list">${comments.length ? comments.map(c => `<div class="list-item"><div><b>${escapeHtml(String(c?.Author ?? c?.author ?? ''))}</b> • ${escapeHtml(String(c?.TimestampUtc ?? c?.timestampUtc ?? ''))}</div><div>${escapeHtml(String(c?.Text ?? c?.text ?? ''))}</div></div>`).join('') : '<div class="muted small">No comments.</div>'}</div></div>
  `;
  wrap.querySelectorAll('[data-mod-action]').forEach(btn => btn.onclick = async () => {
    const action = btn.dataset.modAction;
    if ((action === 'kick' || action === 'ban') && !await confirmAction({
      title: `${action === 'ban' ? 'Ban' : 'Kick'} ticketed player`,
      message: `${action === 'ban' ? 'Ban' : 'Kick'} Steam ID ${moderationSelectedSteamId || '(unknown)'}?`,
      confirmLabel: action === 'ban' ? 'Ban player' : 'Kick player',
      tone: 'danger',
    })) return;
    const res = await apiFetch('/api/moderation/ticket_action', { method:'POST', body: JSON.stringify({ server_id: currentServerId, steam_id: moderationSelectedSteamId, action }) });
    if (!res.ok || !res.data?.success){ notify(res.data?.error || 'Moderation action failed.', 'error'); return; }
    await window.loadModerationPage();
  });
  const commentBtn = document.getElementById('mod-comment-btn');
  if (commentBtn) commentBtn.onclick = async () => {
    const text = document.getElementById('mod-comment-text')?.value || '';
    const res = await apiFetch('/api/moderation/ticket_action', { method:'POST', body: JSON.stringify({ server_id: currentServerId, steam_id: moderationSelectedSteamId, action: 'comment', text }) });
    if (!res.ok || !res.data?.success){ notify(res.data?.error || 'Comment failed.', 'error'); return; }
    await window.loadModerationPage();
  };
}

window.loadModerationPage = async function(){
  if (!currentServerId) return;
  await moderationRefreshStatus();
  const res = await apiFetch('/api/moderation/state');
  if (!res.ok || !res.data?.success){
    moderationState = { tickets: [], closed_tickets: [], settings: {} };
    renderModerationLists();
    renderModerationDetail();
    const hint = document.getElementById('mod-paths-hint');
    if (hint) hint.textContent = res.data?.error || 'Failed to load moderation state. Install the moderation mod to generate config/state files.';
    return;
  }
  moderationState = res.data;
  const s = res.data.settings || {};
  const setChecked = (id,v) => { const el = document.getElementById(id); if (el) el.checked = !!v; };
  const setValue = (id,v) => { const el = document.getElementById(id); if (el) el.value = v ?? ''; };
  if (!moderationFormDirty) {
    setChecked('mod-enable-autokick', s.enable_auto_kick);
    setChecked('mod-bot-notify', s.panel_discord_notifications);
    setValue('mod-aircraft-tol', s.aircraft_tolerance);
    setValue('mod-vehicle-tol', s.vehicle_tolerance);
    setValue('mod-ship-tol', s.ship_tolerance);
  }
  const hint = document.getElementById('mod-paths-hint');
  if (hint) hint.textContent = `Config: ${res.data.cfg_path || 'not found'} | State: ${res.data.state_path || 'not found'}`;
  const all = [...(res.data.tickets||[]), ...(res.data.closed_tickets||[])];
  if (moderationSelectedSteamId && !all.find(t => moderationTicketSteamId(t) === moderationSelectedSteamId)) moderationSelectedSteamId = null;
  if (!moderationSelectedSteamId && (res.data.tickets||[]).length) moderationSelectedSteamId = moderationTicketSteamId(res.data.tickets[0]);
  renderModerationLists();
  renderModerationDetail();
};

document.addEventListener('click', (ev) => {
  const saveBtn = ev.target?.closest?.('#mod-save-btn');
  if (!saveBtn) return;
  (async()=>{
    const payload = {
      server_id: currentServerId,
      enable_auto_kick: !!document.getElementById('mod-enable-autokick')?.checked,
      panel_discord_notifications: !!document.getElementById('mod-bot-notify')?.checked,
      aircraft_tolerance: parseInt(document.getElementById('mod-aircraft-tol')?.value || '0', 10),
      vehicle_tolerance: parseInt(document.getElementById('mod-vehicle-tol')?.value || '1', 10),
      ship_tolerance: parseInt(document.getElementById('mod-ship-tol')?.value || '0', 10),
    };
    const res = await apiFetch('/api/moderation/settings', { method:'POST', body: JSON.stringify(payload) });
    if (!res.ok || !res.data?.success){ notify(res.data?.error || 'Failed to save moderation settings.', 'error'); return; }
    moderationFormDirty = false;
    await window.loadModerationPage();
    try{ pushResponse('Moderation settings saved.'); }catch{}
  })();
});

document.addEventListener('click', (ev) => {
  const btn = ev.target?.closest?.('#mod-refresh-status-btn');
  if (!btn) return;
  (async()=>{ await moderationRefreshStatus(); })();
});

document.addEventListener('click', (ev) => {
  const btn = ev.target?.closest?.('#mod-install-btn');
  if (!btn) return;
  (async()=>{
    if (!currentServerId){ notify('Select a server first.', 'error'); return; }
    if (!await confirmAction({
      title: 'Install moderation module',
      message: 'This installs BepInEx and the public-source moderation module into the selected server.',
      confirmLabel: 'Install module',
    })) return;
    moderationSetInstallLines(['Starting moderation mod install...']);
    moderationSetInstallStatus('Installing moderation mod...');
    const res = await apiFetch('/api/moderation/install', { method:'POST', body: JSON.stringify({ server_id: currentServerId }) });
    if (!res.ok || !res.data?.success){ notify(res.data?.error || 'Failed to start moderation mod install.', 'error'); return; }
    if (moderationInstallPoll){ clearInterval(moderationInstallPoll); }
    moderationInstallPoll = setInterval(moderationPollInstallJob, 1500);
    await moderationPollInstallJob();
  })();
});

document.addEventListener('click', (ev) => {
  const btn = ev.target?.closest?.('#mod-load-btn');
  if (!btn) return;
  moderationFormDirty = false;
  window.loadModerationPage();
});

document.addEventListener('input', (ev) => {
  const el = ev.target;
  if (el && (el.id === 'mod-aircraft-tol' || el.id === 'mod-vehicle-tol' || el.id === 'mod-ship-tol')) {
    moderationFormDirty = true;
  }
});

document.addEventListener('change', (ev) => {
  const el = ev.target;
  if (el && (el.id === 'mod-enable-autokick' || el.id === 'mod-bot-notify')) {
    moderationFormDirty = true;
  }
});
