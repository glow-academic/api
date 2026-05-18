// Debug panel client.
//
// Two independent sub-modules in this one file:
//   1. callsView  — polls /data on this server, patches DOM in place.
//   2. eventsView — connects to the API's socket.io with a JWT and
//                   streams every event via socket.onAny.

const LS_JWT     = "glow-debug-jwt";
const LS_FILTERS = "glow-debug-filters";
const POLL_INTERVAL_MS = 2000;
const MAX_EVENTS = 500;

let API_BASE = "http://localhost:8000";

// ── helpers ─────────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);
const fmtBytes = (n) => {
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(1)} ${u[i]}`;
};
const fmtTs = (sec) => {
  if (!sec) return "—";
  const d = new Date(sec * 1000);
  return d.toLocaleString();
};
const fmtTime = (sec) => {
  if (!sec) return "—";
  return new Date(sec * 1000).toLocaleTimeString([], { hour12: false });
};
const fmtLatency = (ms) => {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
};

// ── 1. CALLS VIEW (left pane) ───────────────────────────────────────────

const callsView = (() => {
  const expanded = new Set();   // call_id → has been opened
  const bodies = new Map();     // call_id → cached JSON body
  let lastSig = "";

  const filters = (() => {
    const saved = JSON.parse(localStorage.getItem(LS_FILTERS) || "{}");
    return {
      since: saved.since || "1d",
      tool: saved.tool || "",
      failures: !!saved.failures,
    };
  })();

  function persistFilters() {
    localStorage.setItem(LS_FILTERS, JSON.stringify(filters));
  }

  function applyFilterUI() {
    $("since").value = filters.since;
    $("tool").value = filters.tool;
    $("failures-only").checked = filters.failures;
  }

  function bindFilters() {
    $("since").addEventListener("change", (e) => {
      filters.since = e.target.value; persistFilters(); poll();
    });
    let toolDebounce;
    $("tool").addEventListener("input", (e) => {
      filters.tool = e.target.value;
      clearTimeout(toolDebounce);
      toolDebounce = setTimeout(() => { persistFilters(); poll(); }, 250);
    });
    $("failures-only").addEventListener("change", (e) => {
      filters.failures = e.target.checked; persistFilters(); poll();
    });
  }

  async function poll() {
    const params = new URLSearchParams({ since: filters.since });
    if (filters.tool) params.set("tool", filters.tool);
    if (filters.failures) params.set("failures", "true");
    let data;
    try {
      const r = await fetch(`/data?${params}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      data = await r.json();
    } catch (e) {
      $("calls-dot").classList.add("off");
      return;
    }
    $("calls-dot").classList.remove("off");

    // Cheap signature so we don't repaint when nothing changed.
    const sig = `${data.total}|${data.failures}|${data.last_mtime}|${(data.recent_activity[0] || {}).call_id || ""}`;
    if (sig === lastSig) return;
    lastSig = sig;

    renderKPIs(data);
    renderTopTools(data.top_tools);
    renderCallList("recent-failures", data.recent_failures, true);
    const failuresH3 = $("failures-h3");
    if (data.recent_failures.length > 0) {
      failuresH3.style.display = "";
      $("failures-count").textContent = `(${data.recent_failures.length})`;
    } else {
      failuresH3.style.display = "none";
    }
    renderCallList("recent-activity", data.recent_activity, false);
    $("activity-count").textContent = `(${data.recent_activity.length})`;
  }

  function renderKPIs(d) {
    const total = d.total;
    const fails = d.failures;
    const rate = total ? (fails / total * 100) : 0;
    $("kpi-total").textContent = total.toLocaleString();
    $("kpi-failures").textContent = `${fails} (${rate.toFixed(1)}%)`;
    $("kpi-disk").textContent = fmtBytes(d.disk_bytes);
    $("kpi-last").textContent = fmtTs(d.last_mtime);
  }

  function renderTopTools(rows) {
    const tbody = $("top-tools");
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="dim">no calls in window</td></tr>`;
      return;
    }
    const peak = rows[0].count || 1;
    tbody.innerHTML = rows.map(r => {
      const okPct = r.count ? ((r.count - r.failures) / r.count * 100) : 0;
      const okClass = okPct >= 99 ? "good" : okPct >= 90 ? "warn" : "bad";
      const barPct = Math.round(100 * r.count / peak);
      const p50 = r.p50_ms == null ? "—" : fmtLatency(r.p50_ms);
      const p95 = r.p95_ms == null ? "—" : fmtLatency(r.p95_ms);
      return `<tr>
        <td class="tool">${escapeHtml(r.tool)}</td>
        <td><div class="bar"><div class="bar-fill" style="width:${barPct}%"></div></div></td>
        <td class="num">${r.count}</td>
        <td class="num ${okClass}">${okPct.toFixed(0)}%</td>
        <td class="num">${p50}</td>
        <td class="num">${p95}</td>
      </tr>`;
    }).join("");
  }

  function renderCallList(containerId, rows, isFailureList) {
    const container = $(containerId);
    // In-place patch: keep matching .call elements, add new at top, drop missing.
    const existing = new Map();
    container.querySelectorAll(".call").forEach(el => {
      existing.set(el.dataset.callId, el);
    });

    const seen = new Set();
    const frag = document.createDocumentFragment();
    for (const r of rows) {
      seen.add(r.call_id);
      let el = existing.get(r.call_id);
      if (!el) {
        el = buildCallRow(r, isFailureList);
      }
      frag.appendChild(el);
    }
    // Remove rows that fell out of the window.
    for (const [id, el] of existing) {
      if (!seen.has(id)) el.remove();
    }
    container.replaceChildren(frag);
  }

  function buildCallRow(r, isFailureList) {
    const el = document.createElement("div");
    el.className = `call ${r.ok ? "ok" : "fail"}`;
    el.dataset.callId = r.call_id;

    const ts = fmtTime(r.mtime);
    const icon = r.ok ? "✓" : "✗";
    const lat = fmtLatency(r.latency_ms);
    const shortId = String(r.call_id).slice(0, 8);
    const reason = isFailureList && r.reason
      ? `<span class="reason">${escapeHtml(String(r.reason).slice(0, 60))}</span>`
      : "";

    el.innerHTML = `
      <div class="row">
        <span class="ts">${ts}</span>
        <span class="status">${icon}</span>
        <span class="tool">${escapeHtml(r.tool)}</span>
        <span class="latency">${lat}</span>
        ${reason}
        <span class="call-id" title="${escapeHtml(String(r.call_id))}">call=${shortId}</span>
      </div>
    `;

    el.querySelector(".row").addEventListener("click", () => toggleCall(el, r.call_id));
    if (expanded.has(r.call_id)) {
      // Re-render expanded body (cached or re-fetch)
      mountBody(el, r.call_id);
    }
    return el;
  }

  async function toggleCall(el, callId) {
    if (expanded.has(callId)) {
      expanded.delete(callId);
      const pre = el.querySelector("pre, .body-loading");
      if (pre) pre.remove();
      return;
    }
    expanded.add(callId);
    await mountBody(el, callId);
  }

  async function mountBody(el, callId) {
    let pre = el.querySelector("pre, .body-loading");
    if (pre) pre.remove();

    if (bodies.has(callId)) {
      const out = document.createElement("pre");
      out.textContent = JSON.stringify(bodies.get(callId), null, 2);
      el.appendChild(out);
      return;
    }
    const loading = document.createElement("div");
    loading.className = "body-loading";
    loading.textContent = "loading…";
    el.appendChild(loading);

    try {
      const r = await fetch(`/calls/${encodeURIComponent(callId)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      bodies.set(callId, body);
      loading.remove();
      const out = document.createElement("pre");
      out.textContent = JSON.stringify(body, null, 2);
      el.appendChild(out);
    } catch (e) {
      loading.textContent = `error: ${e.message}`;
    }
  }

  function start() {
    applyFilterUI();
    bindFilters();
    poll();
    setInterval(poll, POLL_INTERVAL_MS);
  }
  return { start };
})();

// ── 2. EVENTS VIEW (right pane) ────────────────────────────────────────

const eventsView = (() => {
  let socket = null;
  let paused = false;
  let count = 0;
  let rateWindow = []; // timestamps of recent events
  const buffer = [];   // bounded list of event records
  let filterText = "";

  function setStatus(label, cls) {
    const el = $("ws-status");
    el.textContent = label;
    el.className = `status ${cls}`;
    $("events-dot").classList.toggle("off", cls !== "connected");
  }

  function systemLine(text, cls = "") {
    const div = document.createElement("div");
    div.className = `system ${cls}`;
    div.textContent = `[${new Date().toLocaleTimeString([], { hour12: false })}] ${text}`;
    $("events").prepend(div);
  }

  function disconnect() {
    if (socket) {
      try { socket.disconnect(); } catch (e) { /* */ }
      socket = null;
    }
    setStatus("idle", "idle");
  }

  // Pull the JWT out of whatever the user pasted. Three accepted forms:
  //
  //   1. Raw JWT          — ``eyJhbGci…``
  //   2. ``Bearer <jwt>`` — copy from a curl ``Authorization`` header
  //   3. NextAuth session JSON — the ``{"user":…,"id_token":"eyJ…"}``
  //                              blob the dev session prints. Lets the
  //                              user paste straight from the browser
  //                              session without hand-extracting the
  //                              token field.
  //
  // Returns the bare JWT (no "Bearer " prefix) or null if nothing
  // looks like a JWT.
  function extractJwt(raw) {
    const trimmed = raw.trim();
    if (!trimmed) return null;
    // (3) JSON session object
    if (trimmed.startsWith("{")) {
      try {
        const obj = JSON.parse(trimmed);
        const t = obj.id_token || obj.access_token || obj.token;
        if (typeof t === "string" && t.length > 0) {
          return t.replace(/^Bearer\s+/i, "");
        }
      } catch (_e) {
        // Fall through — let the caller surface the error if needed
      }
      return null;
    }
    // (1) and (2)
    return trimmed.replace(/^Bearer\s+/i, "");
  }

  function connect() {
    const raw = $("jwt").value;
    const bearer = extractJwt(raw);
    if (!bearer) {
      systemLine(
        "Paste a JWT, ``Bearer <jwt>``, or a session JSON containing ``id_token``",
        "error",
      );
      return;
    }
    // Echo what we extracted back into the input (replacing the JSON
    // blob with just the JWT) so the user sees what's actually being
    // used and the localStorage value stays compact.
    if ($("jwt").value !== bearer) {
      $("jwt").value = bearer;
    }
    localStorage.setItem(LS_JWT, bearer);
    disconnect();
    setStatus("connecting…", "connecting");
    systemLine(`connecting to ${API_BASE}`);

    // The API's WS connect handler runs auth.token through
    // extract_bearer_token(), which requires the literal "Bearer "
    // prefix. ``extractJwt`` already stripped any prefix; add exactly one.
    socket = io(API_BASE, {
      auth: { token: `Bearer ${bearer}` },
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionAttempts: 3,
      reconnectionDelay: 1000,
    });

    socket.on("connect", () => {
      setStatus(`connected · ${socket.id.slice(0, 8)}`, "connected");
      systemLine(`connected (sid=${socket.id})`);
    });
    socket.on("disconnect", (reason) => {
      setStatus("disconnected", "error");
      systemLine(`disconnected: ${reason}`, "error");
    });
    socket.on("connect_error", (err) => {
      setStatus("error", "error");
      systemLine(`connect_error: ${err.message || err}`, "error");
    });
    socket.onAny((eventName, ...args) => {
      if (paused) return;
      pushEvent(eventName, args);
    });
  }

  function pushEvent(name, args) {
    const now = Date.now();
    rateWindow.push(now);
    while (rateWindow.length && rateWindow[0] < now - 5000) rateWindow.shift();

    count++;
    $("events-count").textContent = `${count.toLocaleString()} events`;
    const rate = rateWindow.length / 5;
    $("events-rate").textContent = rate > 0 ? `~${rate.toFixed(1)}/s` : "";

    const record = { ts: now, name, args };
    buffer.push(record);
    if (buffer.length > MAX_EVENTS) buffer.shift();

    if (filterText && !name.includes(filterText)) return;

    const el = renderEvent(record);
    const list = $("events");
    list.prepend(el);

    // Trim DOM to MAX_EVENTS
    while (list.children.length > MAX_EVENTS) list.removeChild(list.lastChild);
  }

  function renderEvent(rec) {
    const el = document.createElement("div");
    let cls = "event";
    if (rec.name.endsWith(".failed")) cls += " failed";
    else if (rec.name.endsWith(".completed")) cls += " completed";
    el.className = cls;

    const time = new Date(rec.ts).toLocaleTimeString([], { hour12: false });
    el.innerHTML = `
      <span class="ts">${time}</span>
      <span class="name">${escapeHtml(rec.name)}</span>
    `;
    el.addEventListener("click", () => {
      if (el.classList.contains("expanded")) {
        el.classList.remove("expanded");
        const pre = el.querySelector("pre");
        if (pre) pre.remove();
      } else {
        el.classList.add("expanded");
        const pre = document.createElement("pre");
        pre.textContent = JSON.stringify(
          rec.args.length === 1 ? rec.args[0] : rec.args,
          null, 2
        );
        el.appendChild(pre);
      }
    });
    return el;
  }

  function rebuildList() {
    const list = $("events");
    list.replaceChildren();
    for (let i = buffer.length - 1; i >= 0; i--) {
      const rec = buffer[i];
      if (filterText && !rec.name.includes(filterText)) continue;
      list.appendChild(renderEvent(rec));
    }
  }

  function clearAll() {
    buffer.length = 0;
    count = 0;
    rateWindow.length = 0;
    $("events-count").textContent = "0 events";
    $("events-rate").textContent = "";
    $("events").replaceChildren();
  }

  function start() {
    const stored = localStorage.getItem(LS_JWT);
    if (stored) $("jwt").value = stored;

    $("btn-connect").addEventListener("click", connect);
    $("btn-clear").addEventListener("click", () => {
      localStorage.removeItem(LS_JWT);
      $("jwt").value = "";
      disconnect();
      systemLine("cleared stored JWT");
    });
    $("btn-pause").addEventListener("click", () => {
      paused = !paused;
      $("btn-pause").textContent = paused ? "Resume" : "Pause";
    });
    $("btn-clear-events").addEventListener("click", clearAll);

    let filterDebounce;
    $("event-filter").addEventListener("input", (e) => {
      clearTimeout(filterDebounce);
      filterDebounce = setTimeout(() => {
        filterText = e.target.value.trim();
        rebuildList();
      }, 150);
    });

    setStatus("idle", "idle");
  }
  return { start };
})();

// ── shared utils ────────────────────────────────────────────────────────

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// ── boot ────────────────────────────────────────────────────────────────

(async function boot() {
  try {
    const r = await fetch("/config");
    if (r.ok) {
      const cfg = await r.json();
      API_BASE = cfg.api_base || API_BASE;
    }
  } catch (e) { /* keep default */ }
  $("api-base").textContent = `api=${API_BASE}`;

  callsView.start();
  eventsView.start();
})();
