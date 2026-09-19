/**
 * TrialGuard AI — Frontend Application
 * Single-page application in vanilla JavaScript.
 * All data fetched from the server-side API — no hardcoded values.
 */

"use strict";

// ── State ──────────────────────────────────────────────────────────────────
let _session = null;
let _charts = {};
let _currentContext = null; // { type: 'site'|'deviation'|'capa', id: string, label: string }
let _notifications = [];
let _allAuditEvents = [];

// ── Global trial context ────────────────────────────────────────────────────
// Persisted across page navigations; null = "all trials"
let _selectedTrialId = null;
let _selectedMedicineId = null;
let _allMedicines = [];
let _allTrials = [];

/**
 * Append `?trial_id=...` to an API path when a trial is selected.
 * Paths that should NOT be scoped (medicines/trials lookup, auth, audit) are
 * listed in the bypass list.
 */
function _withTrial(path) {
  if (!_selectedTrialId) return path;
  const bypass = ["/api/medicines", "/api/trials", "/api/auth", "/api/audit", "/api/users"];
  if (bypass.some((b) => path.startsWith(b))) return path;
  const sep = path.includes("?") ? "&" : "?";
  return path + sep + "trial_id=" + encodeURIComponent(_selectedTrialId);
}

// ── API layer ──────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const token = localStorage.getItem("tg_token");
  // Auto-inject trial_id for GET requests to scoped endpoints
  const effectivePath = method === "GET" ? _withTrial(path) : path;
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "include",
  };
  if (token) opts.headers["Authorization"] = `Bearer ${token}`;
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(effectivePath, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw { status: res.status, message: data.error || res.statusText, data };
  return data;
}
const get = (p) => api("GET", p);
const post = (p, b) => api("POST", p, b);
const patch = (p, b) => api("PATCH", p, b);

// ── Auth ───────────────────────────────────────────────────────────────────
document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;
  const errEl = document.getElementById("login-error");
  errEl.style.display = "none";
  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  btn.textContent = "Signing in...";
  try {
    const data = await post("/api/auth/login", { email, password });
    _session = data.user;
    localStorage.setItem("tg_token", data.token);
    showApp();
  } catch (err) {
    errEl.textContent = err.message || "Login failed. Check your credentials.";
    errEl.style.display = "block";
  } finally {
    btn.disabled = false;
    btn.textContent = "Sign in";
  }
});

// Demo account quick-fill
document.querySelectorAll(".demo-account").forEach((el) => {
  el.addEventListener("click", () => {
    document.getElementById("email").value = el.dataset.email;
    document.getElementById("password").value = "TrialGuard2026!";
    document.getElementById("login-form").querySelector("button[type=submit]").focus();
  });
});

// Logout
document.getElementById("logout-btn").addEventListener("click", async () => {
  try { await post("/api/auth/logout"); } catch {}
  localStorage.removeItem("tg_token");
  _session = null;
  document.getElementById("app").style.display = "none";
  document.getElementById("login-screen").style.display = "flex";
  document.getElementById("email").value = "";
  document.getElementById("password").value = "";
});

// ── App shell ──────────────────────────────────────────────────────────────
function showApp() {
  document.getElementById("login-screen").style.display = "none";
  document.getElementById("app").style.display = "flex";

  // Set user info
  document.getElementById("user-name").textContent = _session.name;
  const roleEl = document.getElementById("user-role-pill");
  roleEl.textContent = _session.role.replace("_", " ");
  roleEl.className = `user-role-pill demo-role-badge role-${_session.role}`;
  document.getElementById("user-avatar").textContent = _session.name[0];

  // Show admin-only items
  if (_session.role === "SYSTEM_ADMIN") {
    document.querySelectorAll(".admin-only").forEach((el) => (el.style.display = ""));
  }

  // Hide CAPA generate for non-managers
  const capaBtnEl = document.getElementById("btn-generate-capa");
  if (capaBtnEl && !["STUDY_MANAGER", "SYSTEM_ADMIN"].includes(_session.role)) {
    capaBtnEl.style.display = "none";
  }

  initTrialSelector();
  loadPage("dashboard");
  setupNav();
  setupFilters();
  setupBobInput();
  setupGlobalSearch();
  loadNotifications();
}

// ── Trial / Medicine Selector ───────────────────────────────────────────────
async function initTrialSelector() {
  try {
    [_allMedicines, _allTrials] = await Promise.all([
      get("/api/medicines"),
      get("/api/trials"),
    ]);
  } catch {
    return; // non-fatal — selector just stays empty
  }

  const medSel = document.getElementById("medicine-select");
  const trialSel = document.getElementById("trial-select");
  const scopeBadge = document.getElementById("trial-scope-badge");

  // Populate medicine dropdown
  _allMedicines.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m.medicine_id;
    opt.textContent = m.medicine_code + " – " + m.medicine_name.split(" (")[0];
    medSel.appendChild(opt);
  });

  function populateTrials(medicineId) {
    // Clear existing non-default options
    while (trialSel.options.length > 1) trialSel.remove(1);
    const filtered = medicineId
      ? _allTrials.filter((t) => t.medicine_id === medicineId)
      : _allTrials;
    filtered.forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t.trial_id;
      opt.textContent = t.trial_code + " · " + t.trial_name;
      trialSel.appendChild(opt);
    });
  }

  function updateScopeBadge() {
    if (_selectedTrialId) {
      const trial = _allTrials.find((t) => t.trial_id === _selectedTrialId);
      scopeBadge.textContent = trial ? trial.trial_code : _selectedTrialId;
    } else if (_selectedMedicineId) {
      const med = _allMedicines.find((m) => m.medicine_id === _selectedMedicineId);
      scopeBadge.textContent = med ? med.medicine_code + " (all trials)" : "All Trials";
    } else {
      scopeBadge.textContent = "All Trials";
    }
  }

  populateTrials(null);

  medSel.addEventListener("change", () => {
    _selectedMedicineId = medSel.value || null;
    _selectedTrialId = null;
    populateTrials(_selectedMedicineId);
    trialSel.value = "";
    updateScopeBadge();
    loadPage(_currentPage());
  });

  trialSel.addEventListener("change", () => {
    _selectedTrialId = trialSel.value || null;
    updateScopeBadge();
    loadPage(_currentPage());
  });
}

function _currentPage() {
  const active = document.querySelector(".page.active");
  return active ? active.id.replace("page-", "") : "dashboard";
}

// ── Navigation ─────────────────────────────────────────────────────────────
function setupNav() {
  document.querySelectorAll(".nav-item[data-page]").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      loadPage(el.dataset.page);
    });
  });
  document.getElementById("sidebar-toggle").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
  });
  const notifBtn = document.getElementById("notifications-btn");
  if (notifBtn) {
    notifBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const panel = document.getElementById("notifications-panel");
      if (panel) panel.style.display = panel.style.display === "none" ? "block" : "none";
    });
  }
  // Close notifications panel and search results on click outside
  document.addEventListener("click", () => {
    const panel = document.getElementById("notifications-panel");
    if (panel) panel.style.display = "none";
    const searchResults = document.getElementById("global-search-results");
    if (searchResults) searchResults.style.display = "none";
  });
}

function loadPage(page, params) {
  // Close sidebar on mobile
  document.getElementById("sidebar").classList.remove("open");
  // Update nav active state
  document.querySelectorAll(".nav-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.page === page);
  });
  // Hide all pages
  document.querySelectorAll(".page").forEach((el) => el.classList.remove("active"));
  // Show target page
  const pageEl = document.getElementById(`page-${page}`);
  if (pageEl) pageEl.classList.add("active");

  // Update last updated
  document.getElementById("last-updated").textContent = `Updated ${new Date().toLocaleTimeString()}`;

  // Load page data
  switch (page) {
    case "dashboard": loadDashboard(); setPageContext(null); break;
    case "protocol": loadProtocol(); setPageContext(null); break;
    case "sites": loadSites(); setPageContext(null); break;
    case "site-detail": loadSiteDetail(params); setPageContext("site", params, "Site " + params); break;
    case "deviations": loadDeviations(); setPageContext(null); break;
    case "deviation-detail": loadDeviationDetail(params); setPageContext("deviation", params, "Deviation " + params); break;
    case "capa": loadCapa(); setPageContext(null); break;
    case "capa-detail": loadCapaDetail(params); setPageContext("capa", params, "CAPA " + params); break;
    case "reports": renderRecentReports(); loadReportSiteSelector(); setPageContext(null); break;
    case "audit": loadAudit(); setPageContext(null); break;
    case "bob": loadBobTools(); setPageContext(null); break;
    case "settings": loadSettings(); setPageContext(null); break;
  }
}
window.loadPage = loadPage;

// ── Dashboard ──────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const [summary, charts] = await Promise.all([
      get("/api/dashboard/summary"),
      get("/api/dashboard/charts"),
    ]);
    renderKpis(summary);
    renderHighRiskTable(charts.high_risk_sites || []);
    renderCharts(charts);
    // Run all remaining independent fetches in parallel
    await Promise.all([
      loadRecentDeviations(),
      loadProtocolCompliance(),
      loadDashboardAttention(),
      loadSiteHeatmap(),
      loadEmergingSites(),
      loadBlacklistPanel(),
    ]);
    // Show notification badge
    if (summary.high_risk_sites > 0) {
      const badge = document.getElementById("notif-count");
      badge.textContent = summary.high_risk_sites;
      badge.style.display = "flex";
    }
  } catch (err) {
    console.error("Dashboard load failed:", err);
  }
}

function renderKpis(s) {
  const cards = [
    { label: "Total Sites", value: s.total_sites, cls: "kpi-info", sub: "clinical sites enrolled" },
    { label: "Total Patients", value: s.total_patients, cls: "kpi-info", sub: "synthetic records only" },
    { label: "Total Deviations", value: s.total_deviations, cls: "kpi-warn", sub: "all protocol deviations" },
    { label: "Major Deviations", value: s.major_deviations, cls: "kpi-danger", sub: "severity score ≥10" },
    { label: "Minor Deviations", value: s.minor_deviations, cls: "kpi-warn", sub: "severity score 4–9" },
    { label: "Admin. Deviations", value: s.admin_deviations, cls: "kpi-info", sub: "severity score 0–3" },
    { label: "High-Risk Sites", value: s.high_risk_sites, cls: "kpi-danger", sub: "risk score ≥ 65" },
    { label: "Open CAPAs", value: s.open_capas, cls: "kpi-warn", sub: "awaiting action" },
  ];
  document.getElementById("kpi-grid").innerHTML = cards
    .map((c) => `<div class="kpi-card ${c.cls}">
      <div class="kpi-card-label">${c.label}</div>
      <div class="kpi-card-value">${c.value ?? "—"}</div>
      <div class="kpi-card-sub">${c.sub}</div>
    </div>`)
    .join("");
  const subtitle = document.querySelector("#page-dashboard .page-subtitle");
  if (subtitle) subtitle.innerHTML = `Trial risk overview · <span class="data-through">Synthetic data · Data through 18 Sep 2026</span>`;
}

function renderHighRiskTable(sites) {
  const tbody = document.getElementById("high-risk-tbody");
  if (!sites.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="loading-cell">No high-risk sites found.</td></tr>`;
    return;
  }
  tbody.innerHTML = sites.map((s) => `<tr>
    <td><strong>${s.site_id}</strong></td>
    <td>${s.site_name || s.site_id}</td>
    <td>
      <span class="risk-score-cell risk-score-${(s.risk_level || "low").toLowerCase()}">${s.current_score}/100</span>
      <span class="risk-bar"><span class="risk-bar-fill ${(s.risk_level || "low").toLowerCase()}" style="width:${s.current_score}%"></span></span>
    </td>
    <td><span class="badge badge-${s.risk_level}">${s.risk_level}</span></td>
    <td><span class="badge badge-${s.trend}">${s.trend || "STABLE"}</span></td>
    <td>
      <div class="indicator-list">
        ${(s.leading_indicators || []).slice(0, 2).map((i) => `<span class="indicator-chip">${i}</span>`).join("")}
      </div>
    </td>
    <td>
      <button class="btn btn-sm btn-primary" onclick="loadPage('site-detail','${s.site_id}')">Investigate</button>
    </td>
  </tr>`).join("");
}

function renderCharts(data) {
  // Risk distribution donut
  if (_charts["risk-dist"]) _charts["risk-dist"].destroy();
  const rd = document.getElementById("chart-risk-dist");
  if (rd) {
    _charts["risk-dist"] = new Chart(rd, {
      type: "doughnut",
      data: {
        labels: ["HIGH", "MEDIUM", "LOW"],
        datasets: [{
          data: [data.risk_distribution?.HIGH || 0, data.risk_distribution?.MEDIUM || 0, data.risk_distribution?.LOW || 0],
          backgroundColor: ["#dc2626", "#d97706", "#059669"],
          borderWidth: 2, borderColor: "#fff",
        }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { font: { size: 11 } } } } },
    });
  }

  // Deviation trend
  if (_charts["dev-trend"]) _charts["dev-trend"].destroy();
  const dt = document.getElementById("chart-deviation-trend");
  if (dt && data.deviation_trend?.length) {
    const labels = data.deviation_trend.map((t) => t.period);
    _charts["dev-trend"] = new Chart(dt, {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "MAJOR", data: data.deviation_trend.map((t) => t.MAJOR || 0), backgroundColor: "#dc2626" },
          { label: "MINOR", data: data.deviation_trend.map((t) => t.MINOR || 0), backgroundColor: "#d97706" },
          { label: "ADMINISTRATIVE", data: data.deviation_trend.map((t) => t.ADMINISTRATIVE || 0), backgroundColor: "#2563eb" },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
        plugins: { legend: { position: "top", labels: { font: { size: 11 } } } },
      },
    });
  }

  // CAPA status
  if (_charts["capa"]) _charts["capa"].destroy();
  const cs = document.getElementById("chart-capa-status");
  if (cs) {
    const capaData = data.capa_status || {};
    _charts["capa"] = new Chart(cs, {
      type: "doughnut",
      data: {
        labels: Object.keys(capaData),
        datasets: [{ data: Object.values(capaData), backgroundColor: ["#d97706", "#2563eb", "#059669", "#dc2626"], borderWidth: 2, borderColor: "#fff" }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { font: { size: 11 } } } } },
    });
  }

  // Deviation types bar
  if (_charts["dev-types"]) _charts["dev-types"].destroy();
  const dvt = document.getElementById("chart-dev-types");
  if (dvt && data.deviation_by_type) {
    const labels = Object.keys(data.deviation_by_type).map((k) => k.replace(/_/g, " "));
    _charts["dev-types"] = new Chart(dvt, {
      type: "bar",
      data: {
        labels,
        datasets: [{ label: "Count", data: Object.values(data.deviation_by_type), backgroundColor: "#1d4ed8" }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true } },
      },
    });
  }
}

async function loadRecentDeviations() {
  const devs = await get("/api/deviations");
  const recent = devs.slice(0, 10);
  document.getElementById("recent-devs-tbody").innerHTML = recent.map((d) => `<tr>
    <td><button class="btn btn-sm btn-ghost" onclick="loadPage('deviation-detail','${d.deviation_id}')">${d.deviation_id}</button></td>
    <td><button class="btn btn-sm btn-ghost" onclick="loadPage('site-detail','${d.site_id}')">${d.site_id}</button></td>
    <td>${d.patient_id}</td>
    <td>${(d.type || "").replace(/_/g, " ")}</td>
    <td><span class="badge badge-${(d.severity || "").toLowerCase()}">${d.severity}</span></td>
    <td>${d.detected_at || "—"}</td>
    <td><span class="badge badge-${d.status}">${d.status}</span></td>
    <td><button class="btn btn-sm btn-ghost" onclick="loadPage('deviation-detail','${d.deviation_id}')">View</button></td>
  </tr>`).join("");
}

async function loadProtocolCompliance() {
  try {
    const data = await post("/api/protocol/analyze", {});
    const canvas = document.getElementById("chart-compliance");
    if (!canvas) return;
    if (_charts["compliance"]) _charts["compliance"].destroy();
    const items = data.compliance_by_domain || [];
    _charts["compliance"] = new Chart(canvas, {
      type: "bar",
      data: {
        labels: items.map((i) => i.domain),
        datasets: [{ label: "Compliance %", data: items.map((i) => i.compliance_pct), backgroundColor: items.map((i) => i.compliance_pct >= 90 ? "#059669" : i.compliance_pct >= 75 ? "#d97706" : "#dc2626") }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { min: 0, max: 100, ticks: { callback: (v) => v + "%" } } },
      },
    });
  } catch {}
}

// ── Protocol ────────────────────────────────────────────────────────────────
async function loadProtocol() {
  try {
    const protocol = await get("/api/protocol");
    const rules = protocol.rules || [];

    document.getElementById("protocol-rules-list").innerHTML = rules.map((r) => `
      <div class="protocol-rule" id="rule-${r.rule_id}">
        <div class="protocol-rule-header">
          <span class="rule-id">${r.rule_id}</span>
          <span class="rule-domain">${r.domain}</span>
          ${r.severity_if_violated ? `<span class="severity-indicator sev-${r.severity_if_violated}">${r.severity_if_violated}</span>` : ""}
        </div>
        <div class="rule-name">${r.name}</div>
        <div class="rule-expected">Expected: <strong>${r.expected}</strong></div>
        ${r.description ? `<div class="rule-expected" style="margin-top:6px;font-size:11px">${r.description}</div>` : ""}
        <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn btn-sm btn-secondary" onclick="showPatientCompare('${r.rule_id}','${r.name.replace(/'/g,'&#39;')}','${r.expected.replace(/'/g,'&#39;')}')">Compare Patient</button>
          <button class="btn btn-sm btn-ghost" onclick="loadPage('bob');setTimeout(()=>askBob('What is protocol rule ${r.rule_id}?'),200)">Ask Bob</button>
        </div>
        <div id="patient-compare-${r.rule_id}" style="display:none"></div>
      </div>
    `).join("");

    // Protocol compliance
    const complianceData = await post("/api/protocol/analyze", {});
    const domains = complianceData.compliance_by_domain || [];
    document.getElementById("protocol-compliance-list").innerHTML = domains.map((d) => {
      const color = d.compliance_pct >= 90 ? "#059669" : d.compliance_pct >= 75 ? "#d97706" : "#dc2626";
      return `<div class="compliance-item">
        <div class="compliance-header">
          <span>${d.domain}</span>
          <span style="color:${color};font-weight:700">${d.compliance_pct}%</span>
        </div>
        <div class="compliance-bar-track">
          <div class="compliance-bar-fill" style="width:${d.compliance_pct}%;background:${color}"></div>
        </div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:4px">${d.violations} violations</div>
      </div>`;
    }).join("");

    // Visit schedule
    const schedule = protocol.visit_schedule || [];
    document.getElementById("visit-schedule").innerHTML = schedule.map((v) => `
      <div class="visit-item">
        <div class="visit-num">VISIT ${v.visit_number}</div>
        <div class="visit-label">${v.label}</div>
        <div class="visit-window">Window: ±${v.window_tolerance} days</div>
      </div>
    `).join("");
  } catch (err) {
    console.error("Protocol load failed:", err);
  }
}

// ── Sites ──────────────────────────────────────────────────────────────────
let _allSites = [];

async function loadSites() {
  try {
    _allSites = await get("/api/sites");
    renderSitesTable(_allSites);
  } catch (err) {
    document.getElementById("sites-tbody").innerHTML = `<tr><td colspan="10" class="loading-cell">Failed to load sites.</td></tr>`;
  }
}

function renderSitesTable(sites) {
  document.getElementById("sites-tbody").innerHTML = sites.map((s) => {
    const level = s.risk_level || "LOW";
    const score = s.risk_score || 0;
    return `<tr>
      <td><strong>${s.site_id}</strong></td>
      <td>${s.name}</td>
      <td>${s.location}</td>
      <td>${s.investigator}</td>
      <td>${s.patient_count}</td>
      <td>
        <span class="risk-score-cell risk-score-${level.toLowerCase()}">${score}/100</span>
        <span class="risk-bar"><span class="risk-bar-fill ${level.toLowerCase()}" style="width:${score}%"></span></span>
      </td>
      <td><span class="badge badge-${level}">${level}</span></td>
      <td><span class="badge badge-${s.trend || "STABLE"}">${s.trend || "STABLE"}</span></td>
      <td><span class="badge badge-${s.status === "ACTIVE" ? "success" : "major"}">${s.status}</span></td>
      <td><button class="btn btn-sm btn-primary" onclick="loadPage('site-detail','${s.site_id}')">View</button></td>
    </tr>`;
  }).join("") || `<tr><td colspan="10" class="loading-cell">No sites found.</td></tr>`;
}

function setupFilters() {
  document.getElementById("sites-search").addEventListener("input", applyFilters);
  document.getElementById("sites-risk-filter").addEventListener("change", applyFilters);
  document.getElementById("devs-search").addEventListener("input", applyDevFilters);
  document.getElementById("devs-severity-filter").addEventListener("change", applyDevFilters);
  document.getElementById("devs-status-filter").addEventListener("change", applyDevFilters);
  const siteFilter = document.getElementById("devs-site-filter");
  const typeFilter = document.getElementById("devs-type-filter");
  const dateFrom = document.getElementById("devs-date-from");
  const dateTo = document.getElementById("devs-date-to");
  if (siteFilter) siteFilter.addEventListener("change", applyDevFilters);
  if (typeFilter) typeFilter.addEventListener("change", applyDevFilters);
  if (dateFrom) dateFrom.addEventListener("change", applyDevFilters);
  if (dateTo) dateTo.addEventListener("change", applyDevFilters);
  const pageSizeEl = document.getElementById("devs-page-size");
  if (pageSizeEl) pageSizeEl.addEventListener("change", () => {
    _devPageSize = parseInt(pageSizeEl.value, 10) || 10;
    _devCurrentPage = 1;
    _renderDevsPage();
  });
}

function applyFilters() {
  const q = document.getElementById("sites-search").value.toLowerCase();
  const risk = document.getElementById("sites-risk-filter").value;
  const filtered = _allSites.filter((s) => {
    const matchQ = !q || s.site_id.toLowerCase().includes(q) || s.name.toLowerCase().includes(q) || s.location.toLowerCase().includes(q);
    const matchRisk = !risk || s.risk_level === risk;
    return matchQ && matchRisk;
  });
  renderSitesTable(filtered);
}

// ── Site Investigation Workspace ───────────────────────────────────────────
async function loadSiteDetail(siteId) {
  if (!siteId) return;
  const [site, risk, devs, patients, investigation] = await Promise.all([
    get(`/api/sites/${siteId}`),
    get(`/api/sites/${siteId}/risk`),
    get(`/api/sites/${siteId}/deviations`),
    get(`/api/sites/${siteId}/patients`).catch(() => []),
    get(`/api/sites/${siteId}/investigation`).catch(() => null),
  ]);

  // Build blacklist status banner if site is blacklisted
  const blBanner = site.is_blacklisted ? `
    <div class="site-blacklist-header" id="site-bl-header-${siteId}">
      <div class="sbh-title">
        <span class="blacklist-badge">&#128308; BLACKLISTED</span>
        <strong style="color:#7c2d12">Write access restricted</strong>
      </div>
      <div class="sbh-reason"><strong>Reason:</strong> ${escapeHtml(site.blacklist_reason || "No reason provided")}</div>
      <div class="sbh-meta">
        Source: <strong>${_formatBlacklistSource(site.blacklist_source)}</strong>
        &nbsp;&#183;&nbsp; Blacklisted at: <strong>${site.blacklisted_at ? new Date(site.blacklisted_at).toLocaleString() : "&#8212;"}</strong>
        &nbsp;&#183;&nbsp; By: <strong>${escapeHtml(site.blacklisted_by || "&#8212;")}</strong>
      </div>
      <div class="sbh-actions">
        ${_session && ["STUDY_MANAGER","SYSTEM_ADMIN"].includes(_session.role) ? `<button class="btn btn-sm btn-clear-blacklist" onclick="openClearBlacklistModal('${siteId}','${escapeHtml(site.name)}',${risk.current_score||0},'${escapeHtml(site.blacklist_reason||'')}')">&#10003; Clear Blacklist</button>` : ""}
      </div>
    </div>
  ` : `
    <div id="site-bl-header-${siteId}">
      ${_session && ["STUDY_MANAGER","SYSTEM_ADMIN"].includes(_session.role) ? `<div style="margin-bottom:12px"><button class="btn btn-sm btn-blacklist" onclick="openBlacklistModal('${siteId}','${escapeHtml(site.name)}',${risk.current_score||0})">&#128308; Blacklist Site</button></div>` : ""}
    </div>
  `;

  document.getElementById("site-detail-header").innerHTML = `
    ${blBanner}
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
      <div>
        <h2 style="margin:0">${site.name}</h2>
        <div style="color:var(--text-muted);font-size:13px">${site.site_id} · ${site.location} · ${site.investigator}</div>
      </div>
      <span class="badge badge-${risk.risk_level}">${risk.risk_level}</span>
      <button class="btn btn-sm btn-secondary" onclick="loadPage('bob')">Ask IBM Bob</button>
    </div>
  `;

  const sevCounts = { MAJOR: 0, MINOR: 0, ADMINISTRATIVE: 0 };
  devs.forEach((d) => { if (sevCounts[d.severity] !== undefined) sevCounts[d.severity]++; });
  const scoreClass = risk.risk_level === "HIGH" ? "high" : risk.risk_level === "MEDIUM" ? "medium" : "low";
  const sparkline = risk.sparkline || [];

  document.getElementById("site-detail-content").innerHTML = `
    <!-- Hero -->
    <div class="site-risk-hero" style="margin-bottom:24px">
      <div class="site-score-row">
        <div>
          <div class="site-score-big ${scoreClass}">${risk.current_score}</div>
          <div class="site-score-label">Risk Score / 100</div>
        </div>
        <div>
          <div style="margin-bottom:8px">
            <span class="badge badge-${risk.risk_level}" style="font-size:13px;padding:4px 12px">${risk.risk_level} RISK</span>
            &nbsp;
            <span class="badge badge-${risk.trend}">${risk.trend}</span>
          </div>
          <div class="predicted-score">Predicted next period: <strong>${risk.predicted_score}/100</strong></div>
          ${risk.trend === "WORSENING" ? `<div style="color:var(--risk-high);font-size:12px;margin-top:6px">⚠ Site ${siteId} is projected to enter higher risk territory.</div>` : ""}
        </div>
        <div style="flex:1">
          ${sparkline.length > 0 ? `
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:6px">6-Period Risk Trajectory</div>
            <div class="sparkline-cell" style="height:40px;gap:4px">
              ${sparkline.map((v) => `<div class="spark-bar" style="height:${v}%;background:${v > 65 ? "var(--risk-high)" : v > 35 ? "var(--risk-medium)" : "var(--risk-low)"}"></div>`).join("")}
            </div>
          ` : ""}
        </div>
      </div>
      <div class="site-indicators">
        <div class="site-indicators-label">Leading Indicators</div>
        <div class="indicator-list">
          ${(risk.leading_indicators || []).map((i) => `<span class="indicator-chip">${i}</span>`).join("")}
        </div>
      </div>
      ${(risk.risk_drivers || []).length > 0 ? `
        <div class="site-indicators" style="margin-top:12px">
          <div class="site-indicators-label">Risk Drivers</div>
          <ul style="margin:0;padding-left:16px;font-size:13px;color:var(--text)">
            ${risk.risk_drivers.map((d) => `<li>${d}</li>`).join("")}
          </ul>
        </div>
      ` : ""}
    </div>

    <!-- Data grid -->
    <div class="site-data-grid">
      <div class="site-data-panel">
        <h4>Site Overview</h4>
        <div class="detail-row"><span class="detail-label">Site ID</span><span class="detail-value">${site.site_id}</span></div>
        <div class="detail-row"><span class="detail-label">Investigator</span><span class="detail-value">${site.investigator}</span></div>
        <div class="detail-row"><span class="detail-label">Location</span><span class="detail-value">${site.location}</span></div>
        <div class="detail-row"><span class="detail-label">Patients</span><span class="detail-value">${patients.length}</span></div>
        <div class="detail-row"><span class="detail-label">Status</span><span class="detail-value"><span class="badge badge-${site.status === "ACTIVE" ? "success" : "major"}">${site.status}</span></span></div>
      </div>
      <div class="site-data-panel">
        <h4>Deviations (${devs.length})</h4>
        <div class="detail-row"><span class="detail-label">MAJOR</span><span class="detail-value risk-score-high">${sevCounts.MAJOR}</span></div>
        <div class="detail-row"><span class="detail-label">MINOR</span><span class="detail-value risk-score-medium">${sevCounts.MINOR}</span></div>
        <div class="detail-row"><span class="detail-label">ADMINISTRATIVE</span><span class="detail-value" style="color:var(--accent)">${sevCounts.ADMINISTRATIVE}</span></div>
        <button class="btn btn-sm btn-ghost" onclick="loadPage('deviations')" style="margin-top:8px">View deviations →</button>
      </div>
      <div class="site-data-panel">
        <h4>Recommended Actions</h4>
        <button class="btn btn-sm btn-primary" onclick="investigateSiteWithBob('${siteId}')" style="margin-bottom:8px;width:100%">Investigate with Bob</button>
        <button class="btn btn-sm btn-secondary" onclick="loadPage('bob');setTimeout(()=>askBob('Recommend actions for Site ${siteId}'),200)" style="margin-bottom:8px;width:100%">Ask for Recommendations</button>
        <button class="btn btn-sm btn-secondary" onclick="generateReport('site','${siteId}')" style="width:100%;margin-bottom:8px">Generate Site Report</button>
        <button class="btn btn-sm btn-secondary" onclick="openCapaModalForSite('${siteId}')" style="width:100%">Generate CAPA</button>
      </div>
    </div>

    <!-- Deviations at this site -->
    <div class="data-panel">
      <div class="panel-header">
        <h3>Site Deviations</h3>
      </div>
      <div class="table-container">
        <table class="data-table">
          <thead><tr>
            <th>Deviation ID</th><th>Patient</th><th>Type</th><th>Severity</th><th>Expected</th><th>Actual</th><th>Detected</th><th>Status</th><th>Action</th>
          </tr></thead>
          <tbody>
            ${devs.slice(0, 20).map((d) => `<tr>
              <td>${d.deviation_id}</td>
              <td>${d.patient_id}</td>
              <td>${(d.type || "").replace(/_/g, " ")}</td>
              <td><span class="badge badge-${(d.severity || "").toLowerCase()}">${d.severity}</span></td>
              <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis">${d.expected || "—"}</td>
              <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis">${d.actual || "—"}</td>
              <td>${d.detected_at || "—"}</td>
              <td><span class="badge badge-${d.status}">${d.status}</span></td>
              <td><button class="btn btn-sm btn-ghost" onclick="loadPage('deviation-detail','${d.deviation_id}')">View</button></td>
            </tr>`).join("")}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Investigation Workspace (P0-3) -->
    ${investigation ? `
    <div class="data-panel" style="margin-top:20px">
      <div class="panel-header">
        <h3>Investigation Workspace</h3>
        ${investigation.primary_signal ? `<span class="indicator-chip" style="background:var(--risk-high);color:#fff">${escapeHtml(investigation.primary_signal)}</span>` : ""}
      </div>

      <!-- Risk Driver Breakdown -->
      ${(investigation.risk_driver_breakdown || []).length ? `
      <div style="margin-bottom:20px">
        <div class="site-indicators-label" style="margin-bottom:8px">Risk Driver Breakdown</div>
        <div class="risk-driver-bars">
          ${investigation.risk_driver_breakdown.map(r => `
            <div class="driver-row">
              <span class="driver-label">${escapeHtml(r.factor)}</span>
              <div class="driver-bar-wrap">
                <div class="driver-bar" style="width:${r.pct}%;background:${r.pct > 30 ? 'var(--risk-high)' : r.pct > 15 ? 'var(--risk-medium)' : 'var(--risk-low)'}"></div>
              </div>
              <span class="driver-pct">${r.pct}%</span>
            </div>
          `).join("")}
        </div>
      </div>
      ` : ""}

      <!-- Risk History Sparkline -->
      ${(investigation.risk_history || []).length >= 2 ? `
      <div style="margin-bottom:20px">
        <div class="site-indicators-label" style="margin-bottom:8px">6-Period Risk Trajectory</div>
        <div style="display:flex;align-items:flex-end;gap:4px;height:50px">
          ${investigation.risk_history.map((h, i, arr) => {
            const maxScore = Math.max(...arr.map(x => x.risk_score));
            const pct = Math.round((h.risk_score / maxScore) * 100);
            const color = h.risk_score >= 65 ? 'var(--risk-high)' : h.risk_score >= 35 ? 'var(--risk-medium)' : 'var(--risk-low)';
            return `<div title="${h.period}: ${h.risk_score}/100" style="flex:1;background:${color};height:${pct}%;min-height:4px;border-radius:2px 2px 0 0"></div>`;
          }).join("")}
        </div>
        <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--text-muted);margin-top:2px">
          <span>${investigation.risk_history[0].period}</span>
          <span>${investigation.risk_history[investigation.risk_history.length - 1].period}</span>
        </div>
        ${investigation.risk_history.length >= 2 ? (() => {
          const first = investigation.risk_history[0].risk_score;
          const last = investigation.risk_history[investigation.risk_history.length - 1].risk_score;
          const delta = last - first;
          return `<div style="font-size:12px;color:${delta > 0 ? 'var(--risk-high)' : delta < 0 ? 'var(--risk-low)' : 'var(--text-muted)'};margin-top:4px">
            ${delta > 0 ? '↑' : delta < 0 ? '↓' : '→'} ${delta > 0 ? '+' : ''}${delta} points over ${investigation.risk_history.length} periods
          </div>`;
        })() : ""}
      </div>
      ` : ""}

      <!-- Recurrence Analysis -->
      ${(investigation.recurrence?.patterns || []).length ? `
      <div style="margin-bottom:20px">
        <div class="site-indicators-label" style="margin-bottom:8px">Recurrence Analysis</div>
        <div style="font-size:12px">
          ${investigation.recurrence.patterns.slice(0, 5).map(p => `
            <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px;padding:6px;background:var(--surface);border-radius:4px">
              <span style="font-weight:600;min-width:160px">${escapeHtml(p.deviation_type.replace(/_/g, ' '))}</span>
              <span>${p.occurrences} occurrences · ${p.unique_patient_count} patient(s)</span>
              <span class="badge ${p.is_recurring ? 'badge-major' : 'badge-minor'}">${p.is_recurring ? '⚠ RECURRING' : 'ISOLATED'}</span>
            </div>
          `).join("")}
        </div>
      </div>
      ` : ""}

      <!-- Protocol Rules Violated -->
      ${(investigation.protocol_rules_violated || []).length ? `
      <div style="margin-bottom:20px">
        <div class="site-indicators-label" style="margin-bottom:6px">Protocol Rules Violated</div>
        <div class="indicator-list">
          ${investigation.protocol_rules_violated.map(r => `<span class="indicator-chip" style="background:var(--risk-high);color:#fff">${escapeHtml(r)}</span>`).join("")}
        </div>
      </div>
      ` : ""}

      <!-- CAPA Status -->
      ${investigation.capa?.exists ? `
      <div style="margin-bottom:20px">
        <div class="site-indicators-label" style="margin-bottom:6px">CAPA Record</div>
        <div style="font-size:13px">
          <span class="badge badge-${investigation.capa.status}">${escapeHtml(investigation.capa.status)}</span>
          &nbsp;
          <button class="btn btn-sm btn-ghost" onclick="loadPage('capa-detail','${investigation.capa.capa_id}')">${escapeHtml(investigation.capa.capa_id)}</button>
        </div>
      </div>
      ` : ""}

      <!-- Recommendation -->
      ${investigation.recommendation_summary ? `
      <div style="padding:10px;background:var(--surface);border-left:3px solid var(--accent);border-radius:0 4px 4px 0;font-size:13px">
        <strong>Recommendation:</strong> ${escapeHtml(investigation.recommendation_summary)}
      </div>
      ` : ""}
    </div>
    ` : ""}

    <div class="disclaimer-box">⚠ Risk scores are calculated using a prototype multi-factor framework. Predicted scores are estimates, not guaranteed outcomes. All data is synthetic.</div>
  `;

  // ── Blacklist history section (async, appended after main content) ──
  try {
    const auditEvents = await get("/api/audit").catch(() => []);
    const blEvents = auditEvents.filter(
      (e) => ["SITE_BLACKLISTED", "SITE_BLACKLIST_CLEARED"].includes(e.action) && e.resource_id === siteId
    );
    if (blEvents.length > 0) {
      const container = document.getElementById("site-detail-content");
      if (container) {
        container.insertAdjacentHTML("beforeend", `
          <div class="data-panel" style="margin-top:20px">
            <div class="panel-header"><h3>Blacklist History</h3></div>
            <ul class="blacklist-history-timeline">
              ${blEvents.map((e) => `
                <li class="blacklist-history-item">
                  <div class="blacklist-history-icon">${e.action === "SITE_BLACKLISTED" ? "&#128308;" : "&#9989;"}</div>
                  <div class="blacklist-history-content">
                    <div class="blacklist-history-action">${e.action === "SITE_BLACKLISTED" ? "Site Blacklisted" : "Blacklist Cleared"}</div>
                    <div class="blacklist-history-ts">${e.timestamp ? new Date(e.timestamp).toLocaleString() : "&#8212;"}</div>
                    ${e.metadata ? `<div class="blacklist-history-meta">${
                      e.action === "SITE_BLACKLISTED"
                        ? `Reason: ${escapeHtml(e.metadata.reason || "")} &nbsp;&#183;&nbsp; By: ${escapeHtml(e.metadata.actor || e.metadata.blacklisted_by || "SYSTEM")} &nbsp;&#183;&nbsp; Source: ${_formatBlacklistSource(e.metadata.source)}`
                        : `Cleared by: ${escapeHtml(e.metadata.cleared_by || "")} &nbsp;&#183;&nbsp; Reason: ${escapeHtml(e.metadata.reason || "")}`
                    }</div>` : ""}
                  </div>
                </li>
              `).join("")}
            </ul>
          </div>
        `);
      }
    }
  } catch (_) { /* non-critical */ }
}

// ── Blacklist ───────────────────────────────────────────────────────────────────────────

function _formatBlacklistSource(source) {
  const map = {
    AUTOMATIC_RISK_THRESHOLD: "Automatic Risk Threshold",
    STUDY_MANAGER: "Study Manager",
    SYSTEM_ADMIN: "System Admin",
  };
  return map[source] || escapeHtml(source || "Unknown");
}

async function loadBlacklistPanel() {
  const panel = document.getElementById("blacklist-panel");
  if (!panel) return;
  if (!_session) return;

  try {
    if (_session.role === "SITE_COORDINATOR") {
      const siteId = _session.site_id;
      if (!siteId) return;
      const site = await get(`/api/sites/${siteId}`);
      if (site.is_blacklisted) {
        panel.innerHTML = renderCoordinatorBlacklistBanner(site);
        panel.style.display = "block";
      } else {
        panel.style.display = "none";
      }
    } else if (["STUDY_MANAGER", "SYSTEM_ADMIN", "AUDITOR"].includes(_session.role)) {
      const sites = await get("/api/sites/blacklisted");
      if (!sites.length) {
        panel.style.display = "none";
        return;
      }
      panel.innerHTML = renderBlacklistedSitesPanel(sites);
      panel.style.display = "block";
    }
  } catch (e) {
    panel.style.display = "none";
  }
}

function renderCoordinatorBlacklistBanner(site) {
  return `
    <div class="coordinator-blacklist-banner">
      <div class="banner-title">&#9888; Your site is currently blacklisted &#9888;</div>
      <div class="banner-body">
        <strong>Site ${escapeHtml(site.site_id)}</strong> has been blacklisted. Write actions (CAPA generation, updates) are restricted until cleared by a Study Manager or System Admin.
      </div>
      <div class="banner-meta">
        <strong>Reason:</strong> ${escapeHtml(site.blacklist_reason || "No reason provided")}<br>
        <strong>Source:</strong> ${_formatBlacklistSource(site.blacklist_source)}
        &nbsp;&#183;&nbsp; <strong>Blacklisted at:</strong> ${site.blacklisted_at ? new Date(site.blacklisted_at).toLocaleString() : "&#8212;"}
        &nbsp;&#183;&nbsp; <strong>By:</strong> ${escapeHtml(site.blacklisted_by || "SYSTEM")}
      </div>
    </div>
  `;
}

function renderBlacklistedSitesPanel(sites) {
  const canClear = _session && ["STUDY_MANAGER", "SYSTEM_ADMIN"].includes(_session.role);
  return `
    <div class="blacklist-panel">
      <div class="blacklist-panel-title">&#128308; Blacklisted Sites (${sites.length})</div>
      ${sites.map((s) => `
        <div class="blacklist-site-card">
          <div class="blacklist-site-info">
            <div class="blacklist-site-id"><span class="blacklist-badge">&#128308; BLACKLISTED</span> &nbsp; ${escapeHtml(s.site_id)}</div>
            <div class="blacklist-site-name">${escapeHtml(s.name || "")}</div>
            <div class="blacklist-site-reason"><strong>Reason:</strong> ${escapeHtml(s.blacklist_reason || "")}</div>
            <div class="blacklist-site-meta">
              Source: <strong>${_formatBlacklistSource(s.blacklist_source)}</strong>
              &nbsp;&#183;&nbsp; Blacklisted: <strong>${s.blacklisted_at ? new Date(s.blacklisted_at).toLocaleString() : "&#8212;"}</strong>
              &nbsp;&#183;&nbsp; By: <strong>${escapeHtml(s.blacklisted_by || "SYSTEM")}</strong>
              &nbsp;&#183;&nbsp; Risk Score: <strong>${s.risk_score}</strong>
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end">
            <button class="btn btn-sm btn-secondary" onclick="loadPage('site-detail','${escapeHtml(s.site_id)}')">&#128270; Investigate</button>
            ${canClear ? `<button class="btn btn-sm btn-clear-blacklist" onclick="openClearBlacklistModal('${escapeHtml(s.site_id)}','${escapeHtml(s.name||"")}',${s.risk_score||0},'${escapeHtml(s.blacklist_reason||"")}')">&#10003; Clear Blacklist</button>` : ""}
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

function openBlacklistModal(siteId, siteName, riskScore) {
  const existing = document.getElementById("bl-modal");
  if (existing) existing.remove();

  const modal = document.createElement("div");
  modal.id = "bl-modal";
  modal.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center";
  modal.innerHTML = `
    <div style="background:#fff;border-radius:var(--radius-lg);padding:28px;max-width:480px;width:90%;box-shadow:var(--shadow-lg)">
      <h3 style="margin-bottom:4px">&#128308; Blacklist Site</h3>
      <div style="color:var(--text-muted);font-size:13px;margin-bottom:16px">${escapeHtml(siteId)} &mdash; ${escapeHtml(siteName)} &nbsp;&#183;&nbsp; Risk Score: <strong>${riskScore}</strong></div>
      <div class="form-group">
        <label for="bl-reason-input">Reason for blacklisting <span style="color:var(--risk-high)">*</span></label>
        <textarea id="bl-reason-input" rows="3" placeholder="Describe the reason for blacklisting this site..." style="resize:vertical"></textarea>
      </div>
      <div id="bl-modal-error" style="color:var(--risk-high);font-size:13px;margin-bottom:8px;display:none"></div>
      <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:8px">
        <button class="btn btn-secondary" onclick="document.getElementById('bl-modal').remove()">Cancel</button>
        <button class="btn btn-blacklist" id="bl-confirm-btn">&#128308; Blacklist Site</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  document.getElementById("bl-confirm-btn").onclick = async () => {
    const reason = document.getElementById("bl-reason-input").value.trim();
    const errEl = document.getElementById("bl-modal-error");
    if (!reason) { errEl.textContent = "Reason is required."; errEl.style.display = "block"; return; }
    errEl.style.display = "none";
    try {
      await post(`/api/sites/${siteId}/blacklist`, { reason });
      modal.remove();
      await loadBlacklistPanel();
      await loadSiteDetail(siteId);
    } catch (e) {
      errEl.textContent = e.message || "Failed to blacklist site.";
      errEl.style.display = "block";
    }
  };
}

function openClearBlacklistModal(siteId, siteName, riskScore, currentReason) {
  const existing = document.getElementById("clbl-modal");
  if (existing) existing.remove();

  const warnHtml = riskScore >= 90
    ? `<div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:var(--radius);padding:10px 14px;font-size:13px;color:#92400e;margin-bottom:16px">&#9888; Current risk score (${riskScore}) is still at or above the blacklist threshold (90). Clearing will restore coordinator write access.</div>`
    : "";

  const modal = document.createElement("div");
  modal.id = "clbl-modal";
  modal.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center";
  modal.innerHTML = `
    <div style="background:#fff;border-radius:var(--radius-lg);padding:28px;max-width:480px;width:90%;box-shadow:var(--shadow-lg)">
      <h3 style="margin-bottom:4px">&#9989; Clear Blacklist</h3>
      <div style="color:var(--text-muted);font-size:13px;margin-bottom:16px">${escapeHtml(siteId)} &mdash; ${escapeHtml(siteName)}</div>
      <div style="font-size:13px;margin-bottom:12px;color:var(--text)"><strong>Current blacklist reason:</strong> ${escapeHtml(currentReason || "&#8212;")}</div>
      ${warnHtml}
      <div class="form-group">
        <label for="clbl-reason-input">Reason for clearing <span style="color:var(--risk-high)">*</span></label>
        <textarea id="clbl-reason-input" rows="3" placeholder="Describe why the blacklist is being cleared..." style="resize:vertical"></textarea>
      </div>
      <div id="clbl-modal-error" style="color:var(--risk-high);font-size:13px;margin-bottom:8px;display:none"></div>
      <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:8px">
        <button class="btn btn-secondary" onclick="document.getElementById('clbl-modal').remove()">Cancel</button>
        <button class="btn btn-clear-blacklist" id="clbl-confirm-btn">&#9989; Clear Blacklist</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  document.getElementById("clbl-confirm-btn").onclick = async () => {
    const reason = document.getElementById("clbl-reason-input").value.trim();
    const errEl = document.getElementById("clbl-modal-error");
    if (!reason) { errEl.textContent = "Reason is required."; errEl.style.display = "block"; return; }
    errEl.style.display = "none";
    try {
      await post(`/api/sites/${siteId}/clear-blacklist`, { reason });
      modal.remove();
      await loadBlacklistPanel();
      await loadSiteDetail(siteId);
    } catch (e) {
      errEl.textContent = e.message || "Failed to clear blacklist.";
      errEl.style.display = "block";
    }
  };
}

// ── Deviations ─────────────────────────────────────────────────────────────
let _allDevs = [];
let _devCurrentPage = 1;
let _devPageSize = 10;
let _devFilteredCache = [];

async function loadDeviations() {
  try {
    _allDevs = await get("/api/deviations");
    // Populate site filter
    const siteFilter = document.getElementById("devs-site-filter");
    if (siteFilter && _allDevs.length) {
      const sites = [...new Set(_allDevs.map((d) => d.site_id))].sort();
      siteFilter.innerHTML = `<option value="">All sites</option>` + sites.map((s) => `<option value="${s}">${s}</option>`).join("");
    }
    _devCurrentPage = 1;
    _devFilteredCache = _allDevs;
    _renderDevsPage();
  } catch {}
}

/** Render exactly one page of rows, plus update the pagination footer. */
function _renderDevsPage() {
  const total = _devFilteredCache.length;
  const totalPages = Math.max(1, Math.ceil(total / _devPageSize));
  if (_devCurrentPage > totalPages) _devCurrentPage = totalPages;

  const start = (_devCurrentPage - 1) * _devPageSize;
  const end   = Math.min(start + _devPageSize, total);
  const slice = _devFilteredCache.slice(start, end);

  // Rows
  document.getElementById("devs-tbody").innerHTML = slice.map((d) => `<tr>
    <td><button class="btn btn-sm btn-ghost" onclick="loadPage('deviation-detail','${d.deviation_id}')">${d.deviation_id}</button></td>
    <td><button class="btn btn-sm btn-ghost" onclick="loadPage('site-detail','${d.site_id}')">${d.site_id}</button></td>
    <td>${d.patient_id}</td>
    <td>${(d.type || "").replace(/_/g, " ")}</td>
    <td><span class="badge badge-${(d.severity || "").toLowerCase()}">${d.severity}</span></td>
    <td>${d.severity_score ?? "—"}</td>
    <td>${d.detected_at || "—"}</td>
    <td><span class="badge badge-${d.status}">${d.status}</span></td>
    <td><button class="btn btn-sm btn-ghost" onclick="loadPage('deviation-detail','${d.deviation_id}')">View</button></td>
  </tr>`).join("") || `<tr><td colspan="9" class="loading-cell">No deviations match the filter.</td></tr>`;

  // Summary text
  const summaryEl = document.getElementById("devs-page-summary");
  if (summaryEl) {
    summaryEl.textContent = total === 0
      ? "No deviations match the filter."
      : `Showing ${start + 1}–${end} of ${total} deviation${total !== 1 ? "s" : ""}`;
  }

  // Rows-per-page selector sync
  const sizeEl = document.getElementById("devs-page-size");
  if (sizeEl) sizeEl.value = String(_devPageSize);

  // Page buttons
  const paginatorEl = document.getElementById("devs-paginator");
  if (!paginatorEl) return;

  const prevDisabled = _devCurrentPage <= 1 ? "disabled" : "";
  const nextDisabled = _devCurrentPage >= totalPages ? "disabled" : "";

  let pageButtons = "";
  if (totalPages <= 7) {
    // Show all page numbers
    for (let i = 1; i <= totalPages; i++) {
      pageButtons += _pageBtn(i, _devCurrentPage);
    }
  } else {
    // Smart ellipsis: always show first, last, and window around current
    const pages = _pageWindow(_devCurrentPage, totalPages);
    let prev = 0;
    for (const p of pages) {
      if (p - prev > 1) pageButtons += `<span class="pag-ellipsis" aria-hidden="true">…</span>`;
      pageButtons += _pageBtn(p, _devCurrentPage);
      prev = p;
    }
  }

  paginatorEl.innerHTML = `
    <button class="pag-btn pag-nav" ${prevDisabled} aria-label="Previous page"
      onclick="_devGoPage(${_devCurrentPage - 1})">‹ Prev</button>
    ${pageButtons}
    <button class="pag-btn pag-nav" ${nextDisabled} aria-label="Next page"
      onclick="_devGoPage(${_devCurrentPage + 1})">Next ›</button>
  `;
}

function _pageBtn(n, current) {
  const active = n === current ? " pag-active" : "";
  return `<button class="pag-btn${active}" aria-label="Page ${n}" aria-current="${n === current ? 'page' : 'false'}"
    onclick="_devGoPage(${n})">${n}</button>`;
}

/** Returns array of page numbers to show (first, last, +/- 2 around current). */
function _pageWindow(current, total) {
  const set = new Set([1, 2, total - 1, total, current - 1, current, current + 1]);
  return [...set].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
}

function _devGoPage(n) {
  const totalPages = Math.max(1, Math.ceil(_devFilteredCache.length / _devPageSize));
  _devCurrentPage = Math.max(1, Math.min(n, totalPages));
  _renderDevsPage();
  // Scroll table back into view
  document.getElementById("devs-table")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
window._devGoPage = _devGoPage;

function _getFilteredDevs() {
  const q = document.getElementById("devs-search").value.toLowerCase();
  const sev = document.getElementById("devs-severity-filter").value;
  const status = document.getElementById("devs-status-filter").value;
  const site = (document.getElementById("devs-site-filter") || {}).value || "";
  const type = (document.getElementById("devs-type-filter") || {}).value || "";
  const dateFrom = (document.getElementById("devs-date-from") || {}).value || "";
  const dateTo = (document.getElementById("devs-date-to") || {}).value || "";
  return _allDevs.filter((d) => {
    const matchQ = !q || d.deviation_id.toLowerCase().includes(q) || d.site_id.toLowerCase().includes(q) || d.patient_id.toLowerCase().includes(q) || (d.type || "").toLowerCase().includes(q);
    const matchSev = !sev || d.severity === sev;
    const matchStatus = !status || d.status === status;
    const matchSite = !site || d.site_id === site;
    const matchType = !type || d.type === type;
    const detected = d.detected_at || "";
    const matchFrom = !dateFrom || detected >= dateFrom;
    const matchTo = !dateTo || detected <= dateTo;
    return matchQ && matchSev && matchStatus && matchSite && matchType && matchFrom && matchTo;
  });
}

function applyDevFilters() {
  _devCurrentPage = 1;  // always reset to page 1 on filter change
  _devFilteredCache = _getFilteredDevs();
  _renderDevsPage();
}

function resetDevFilters() {
  ["devs-search", "devs-severity-filter", "devs-status-filter", "devs-site-filter", "devs-type-filter", "devs-date-from", "devs-date-to"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.value = "";
  });
  _devCurrentPage = 1;
  _devFilteredCache = _allDevs;
  _renderDevsPage();
}
window.resetDevFilters = resetDevFilters;

async function loadDeviationDetail(devId) {
  if (!devId) return;
  try {
    const dev = await get(`/api/deviations/${devId}`);
    const factors = dev.factors || {};
    document.getElementById("deviation-detail-content").innerHTML = `
      <div style="margin-bottom:24px">
        <h2 style="margin:0">${dev.deviation_id}</h2>
        <div style="color:var(--text-muted);font-size:13px;margin-top:4px">
          Site: <strong>${dev.site_id}</strong> · Patient: <strong>${dev.patient_id}</strong> · Detected: ${dev.detected_at}
        </div>
      </div>

      <div class="expected-actual-box">
        <div class="ea-box expected">
          <div class="ea-label expected">Expected (Protocol)</div>
          <div class="ea-value">${dev.expected || "—"}</div>
        </div>
        <div class="ea-box actual">
          <div class="ea-label actual">Actual (Observed)</div>
          <div class="ea-value">${dev.actual || "—"}</div>
        </div>
      </div>

      <div class="deviation-detail-grid">
        <div class="detail-card">
          <h4>Deviation Details</h4>
          <div class="detail-row"><span class="detail-label">Type</span><span class="detail-value">${(dev.type || "").replace(/_/g, " ")}</span></div>
          <div class="detail-row"><span class="detail-label">Severity</span><span class="detail-value"><span class="badge badge-${(dev.severity || "").toLowerCase()}">${dev.severity}</span></span></div>
          <div class="detail-row"><span class="detail-label">Severity Score</span><span class="detail-value">${dev.severity_score ?? "—"} / 25</span></div>
          <div class="detail-row"><span class="detail-label">Status</span><span class="detail-value"><span class="badge badge-${dev.status}">${dev.status}</span></span></div>
          <div class="detail-row"><span class="detail-label">Description</span><span class="detail-value">${dev.description || "—"}</span></div>
          ${dev.severity_reason ? `<div class="detail-row" style="flex-direction:column;gap:4px">
            <span class="detail-label">Severity Reasoning</span>
            <span class="detail-value" style="font-size:12px;color:var(--text-muted)">${dev.severity_reason}</span>
          </div>` : ""}
          ${Object.keys(factors).length ? `
            <div class="severity-breakdown">
              <div class="severity-breakdown-title">Severity Factor Breakdown</div>
              ${Object.entries(factors).map(([k, v]) => {
                const maxVal = { safety_impact: 5, data_integrity: 5, protocol_criticality: 4, participant_rights: 5, magnitude: 3, recurrence: 3 }[k] || 5;
                return `<div class="factor-row">
                  <span class="factor-name">${k.replace(/_/g, " ")}</span>
                  <div class="factor-bar-wrap"><div class="factor-bar" style="width:${(v / maxVal) * 100}%"></div></div>
                  <span class="factor-val">${v}/${maxVal}</span>
                </div>`;
              }).join("")}
            </div>
          ` : ""}
        </div>
        <div class="detail-card">
          <h4>Evidence</h4>
          ${dev.evidence ? `
            <div class="detail-row"><span class="detail-label">Protocol</span><span class="detail-value">${dev.evidence.protocol_id}</span></div>
            <div class="detail-row"><span class="detail-label">Rule</span><span class="detail-value">${dev.evidence.rule_id}</span></div>
            <div class="detail-row"><span class="detail-label">Comparison</span><span class="detail-value">${dev.evidence.comparison}</span></div>
          ` : "<p class='text-muted'>No evidence data.</p>"}
          ${(dev.risk_factors || []).length ? `
            <div style="margin-top:16px">
              <div class="detail-label" style="margin-bottom:6px">Risk Factors</div>
              <div class="indicator-list">
                ${dev.risk_factors.map((f) => `<span class="indicator-chip">${f}</span>`).join("")}
              </div>
            </div>
          ` : ""}
          <div style="margin-top:16px">
            <button class="btn btn-sm btn-primary" onclick="loadPage('bob');setTimeout(()=>askBob('Explain deviation ${dev.deviation_id} at site ${dev.site_id}'),200)">Ask Bob About This</button>
          </div>
        </div>
      </div>

      <!-- Evidence Chain (P0-6) -->
      ${(dev.protocol_rule || dev.risk_contribution !== undefined || (dev.related_deviations || []).length) ? `
      <div class="data-panel" style="margin-top:20px">
        <div class="panel-header"><h3>Evidence Chain</h3></div>
        <div class="evidence-chain" style="font-size:12px;padding:12px;background:var(--surface);border-radius:6px;font-family:monospace;line-height:2">
          ${dev.protocol_rule ? `<span class="ec-node ec-rule">Protocol ${dev.evidence?.protocol_id || 'TG-101'} Rule ${dev.evidence?.rule_id || '?'}</span> <span class="ec-arrow">→</span> ` : ""}
          <span class="ec-node ec-expected">Expected: ${escapeHtml(dev.expected || '—')}</span> <span class="ec-arrow">→</span>
          <span class="ec-node ec-patient">Patient ${dev.patient_id}</span> <span class="ec-arrow">→</span>
          <span class="ec-node ec-actual">Actual: ${escapeHtml(dev.actual || '—')}</span> <span class="ec-arrow">→</span>
          <span class="ec-node ec-deviation">${dev.deviation_id}</span> <span class="ec-arrow">→</span>
          <span class="ec-node ec-severity badge badge-${(dev.severity || '').toLowerCase()}">${dev.severity}</span> <span class="ec-arrow">→</span>
          <span class="ec-node ec-site">Site ${dev.site_id}</span>
          ${dev.risk_contribution !== undefined ? ` <span class="ec-arrow">→</span> <span class="ec-node ec-risk">Risk contribution +${dev.risk_contribution}</span>` : ""}
        </div>
        ${dev.protocol_rule ? `
        <div style="margin-top:12px;font-size:12px">
          <strong>Protocol Rule ${dev.protocol_rule.rule_id}:</strong> ${escapeHtml(dev.protocol_rule.name || '')} —
          <em>${escapeHtml(dev.protocol_rule.expected || '')}</em>
        </div>
        ` : ""}
        ${(dev.related_deviations || []).length ? `
        <div style="margin-top:12px">
          <div class="detail-label" style="margin-bottom:6px">Related deviations of same type at this site (${dev.affected_patient_count || 0} patients affected)</div>
          <div style="font-size:12px">
            ${dev.related_deviations.map(r => `
              <button class="btn btn-sm btn-ghost" onclick="loadPage('deviation-detail','${escapeHtml(r.deviation_id)}')" style="margin:2px">
                ${escapeHtml(r.deviation_id)} [${escapeHtml(r.severity || '?')}] ${escapeHtml(r.detected_at || '')}
              </button>
            `).join("")}
          </div>
        </div>
        ` : ""}
        ${dev.capa_id ? `
        <div style="margin-top:8px;font-size:12px">
          <strong>CAPA:</strong>
          <button class="btn btn-sm btn-ghost" onclick="loadPage('capa-detail','${escapeHtml(dev.capa_id)}')">${escapeHtml(dev.capa_id)}</button>
        </div>
        ` : ""}
      </div>
      ` : ""}

      <div class="disclaimer-box">⚠ Severity classification is a prototype framework. Not ICH/FDA/EMA guidance.</div>
    `;
  } catch (err) {
    document.getElementById("deviation-detail-content").innerHTML = `<div class="disclaimer-box">Error loading deviation: ${err.message}</div>`;
  }
}

// ── CAPA ───────────────────────────────────────────────────────────────────
let _capaSiteId = null;

async function loadCapa() {
  try {
    const records = await get("/api/capa");
    const totals = { total: records.length, open: 0, progress: 0, completed: 0, overdue: 0 };
    records.forEach((c) => {
      if (c.status === "OPEN") totals.open++;
      else if (c.status === "IN_PROGRESS") totals.progress++;
      else if (c.status === "COMPLETED") totals.completed++;
      else if (c.status === "OVERDUE") totals.overdue++;
    });

    document.getElementById("capa-kpi-grid").innerHTML = [
      { label: "Total CAPAs", value: totals.total, cls: "kpi-info" },
      { label: "Open", value: totals.open, cls: "kpi-warn" },
      { label: "In Progress", value: totals.progress, cls: "kpi-info" },
      { label: "Completed", value: totals.completed, cls: "kpi-ok" },
    ].map((c) => `<div class="kpi-card ${c.cls}"><div class="kpi-card-label">${c.label}</div><div class="kpi-card-value">${c.value}</div></div>`).join("");

    document.getElementById("capa-tbody").innerHTML = records.map((c) => {
      const dueDate = c.due_date ? new Date(c.due_date) : null;
      const today = new Date();
      const daysRemaining = dueDate ? Math.ceil((dueDate - today) / (1000 * 60 * 60 * 24)) : null;
      const daysHtml = daysRemaining !== null
        ? (daysRemaining < 0
          ? `<span class="days-overdue">${Math.abs(daysRemaining)}d overdue</span>`
          : `<span class="days-remaining">${daysRemaining}d left</span>`)
        : "—";
      return `<tr>
        <td><button class="btn btn-sm btn-ghost" onclick="loadPage('capa-detail','${c.capa_id}')">${c.capa_id}</button></td>
        <td>${c.site_id}</td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.problem_statement}</td>
        <td><span class="badge badge-${(c.priority || "").toLowerCase() === "high" ? "major" : (c.priority || "").toLowerCase() === "medium" ? "minor" : "admin"}">${c.priority}</span></td>
        <td>${c.owner}</td>
        <td><span class="badge badge-${c.status}">${c.status}</span></td>
        <td>${(c.created_at || "").split("T")[0]}</td>
        <td>${c.due_date || "—"}</td>
        <td>${daysHtml}</td>
        <td>
          <button class="btn btn-sm btn-ghost" onclick="loadPage('capa-detail','${c.capa_id}')">View</button>
          ${["STUDY_MANAGER", "SYSTEM_ADMIN", "SITE_COORDINATOR"].includes(_session?.role) ? `<button class="btn btn-sm btn-ghost" onclick="openCapaStatusModal('${c.capa_id}','${c.status}')">Update</button>` : ""}
        </td>
      </tr>`;
    }).join("") || `<tr><td colspan="10" class="loading-cell">No CAPA records found.</td></tr>`;
  } catch (err) {
    document.getElementById("capa-tbody").innerHTML = `<tr><td colspan="10" class="loading-cell">Error: ${err.message}</td></tr>`;
  }
}

async function loadCapaDetail(capaId) {
  if (!capaId) return;
  try {
    const c = await get(`/api/capa/${capaId}`);
    document.getElementById("capa-detail-content").innerHTML = `
      <div style="margin-bottom:24px">
        <h2 style="margin:0">${c.capa_id}</h2>
        <div style="color:var(--text-muted);font-size:13px;margin-top:4px">
          Site: <strong>${c.site_id}</strong> · Priority: <strong>${c.priority}</strong> · Status: <span class="badge badge-${c.status}">${c.status}</span>
        </div>
      </div>
      <div class="disclaimer-box" style="margin-bottom:24px">⚠ ${c.disclaimer || "AI-generated suggestions require qualified clinical and regulatory review before implementation."}</div>
      <div class="capa-detail-grid">
        <div>
          <div class="detail-card" style="margin-bottom:20px">
            <h4>Problem Statement</h4>
            <p>${c.problem_statement}</p>
          </div>
          <div class="detail-card" style="margin-bottom:20px">
            <h4>Root Cause Hypothesis (AI-generated — requires review)</h4>
            <p style="color:var(--text-muted)">${c.root_cause}</p>
          </div>
          <div class="detail-card" style="margin-bottom:20px">
            <h4>Corrective Actions</h4>
            <ul class="action-list">
              ${(c.corrective_actions || []).map((a) => `<li>${a}</li>`).join("")}
            </ul>
          </div>
          <div class="detail-card">
            <h4>Preventive Actions</h4>
            <ul class="action-list">
              ${(c.preventive_actions || []).map((a) => `<li>${a}</li>`).join("")}
            </ul>
          </div>
        </div>
        <div>
          <div class="detail-card" style="margin-bottom:20px">
            <h4>CAPA Metadata</h4>
            <div class="detail-row"><span class="detail-label">CAPA ID</span><span class="detail-value">${c.capa_id}</span></div>
            <div class="detail-row"><span class="detail-label">Site</span><span class="detail-value">${c.site_id}</span></div>
            <div class="detail-row"><span class="detail-label">Priority</span><span class="detail-value">${c.priority}</span></div>
            <div class="detail-row"><span class="detail-label">Owner</span><span class="detail-value">${c.owner}</span></div>
            <div class="detail-row"><span class="detail-label">Status</span><span class="detail-value"><span class="badge badge-${c.status}">${c.status}</span></span></div>
            <div class="detail-row"><span class="detail-label">Due Date</span><span class="detail-value">${c.due_date || "—"}</span></div>
            <div class="detail-row"><span class="detail-label">Created</span><span class="detail-value">${(c.created_at || "").split("T")[0]}</span></div>
            <div class="detail-row"><span class="detail-label">Deviations</span><span class="detail-value">${(c.deviation_ids || []).length} linked</span></div>
          </div>
          <div class="detail-card">
            <h4>CAPA Workflow</h4>
            <div class="capa-workflow" style="padding:12px 0;overflow-x:auto">
              ${['Issue Identified','Evidence','Root Cause','Corrective Actions','Preventive Actions','Review','Approval'].map((step, i) => {
                const statusMap = {'OPEN':1,'IN_PROGRESS':4,'COMPLETED':6,'OVERDUE':1};
                const currentStepIdx = statusMap[c.status] || 0;
                const stepCls = i < currentStepIdx ? 'done' : (i === currentStepIdx ? 'active' : '');
                return `<div class="capa-workflow-step">
                  <div class="capa-step-dot ${stepCls}">${i < currentStepIdx ? '✓' : i+1}</div>
                  <div class="capa-step-label ${stepCls}">${step}</div>
                </div>`;
              }).join('')}
            </div>
          </div>
          <div class="detail-card" style="margin-top:16px">
            <h4>Actions</h4>
            ${["STUDY_MANAGER", "SYSTEM_ADMIN"].includes(_session?.role) ? `
              <button class="btn btn-primary btn-full" style="margin-bottom:8px" onclick="submitCapaAction('${c.capa_id}','COMPLETED')">✓ Approve CAPA</button>
              <button class="btn btn-danger btn-full" style="margin-bottom:8px" onclick="submitCapaAction('${c.capa_id}','OPEN')">✗ Reject / Reopen</button>
            ` : ""}
            ${["SITE_COORDINATOR"].includes(_session?.role) ? `
              <button class="btn btn-secondary btn-full" style="margin-bottom:8px" onclick="openCapaStatusModal('${c.capa_id}','${c.status}')">Update Status</button>
            ` : ""}
            <button class="btn btn-secondary btn-full" style="margin-bottom:8px" onclick="openCapaStatusModal('${c.capa_id}','${c.status}')">Change Status</button>
            <button class="btn btn-ghost btn-full" onclick="generateReport('site','${c.site_id}')">Site Report</button>
            <button class="btn btn-ghost btn-full" style="margin-top:8px" onclick="loadPage('bob');setTimeout(()=>askBob('Explain CAPA ${c.capa_id} for site ${c.site_id}'),200)">Ask Bob</button>
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    document.getElementById("capa-detail-content").innerHTML = `<div class="disclaimer-box">Error: ${err.message}</div>`;
  }
}

function showCapaGenerateModal() {
  const select = document.getElementById("capa-site-select");
  select.innerHTML = `<option value="">Select a site...</option>` +
    (_allSites.length ? _allSites : []).map((s) => `<option value="${s.site_id}">${s.site_id} — ${s.name}</option>`).join("");
  document.getElementById("capa-modal").style.display = "flex";
  if (!_allSites.length) {
    get("/api/sites").then((sites) => {
      _allSites = sites;
      select.innerHTML = `<option value="">Select a site...</option>` +
        sites.map((s) => `<option value="${s.site_id}">${s.site_id} — ${s.name}</option>`).join("");
    }).catch(() => {});
  }
}
window.showCapaGenerateModal = showCapaGenerateModal;

function openCapaModalForSite(siteId) {
  showCapaGenerateModal();
  setTimeout(() => { document.getElementById("capa-site-select").value = siteId; }, 100);
}
window.openCapaModalForSite = openCapaModalForSite;

async function generateCapa() {
  const siteId = document.getElementById("capa-site-select").value;
  if (!siteId) {
    document.getElementById("capa-modal-error").textContent = "Please select a site.";
    document.getElementById("capa-modal-error").style.display = "block";
    return;
  }
  document.getElementById("capa-modal-error").style.display = "none";
  try {
    const record = await post("/api/capa/generate", { site_id: siteId });
    closeModal("capa-modal");
    loadPage("capa-detail", record.capa_id);
  } catch (err) {
    document.getElementById("capa-modal-error").textContent = err.message;
    document.getElementById("capa-modal-error").style.display = "block";
  }
}
window.generateCapa = generateCapa;

function openCapaStatusModal(capaId, currentStatus) {
  document.getElementById("capa-update-id").value = capaId;
  document.getElementById("capa-new-status").value = currentStatus;
  document.getElementById("capa-status-modal").style.display = "flex";
}
window.openCapaStatusModal = openCapaStatusModal;

async function submitCapaAction(capaId, newStatus) {
  const confirmMsg = newStatus === 'COMPLETED' ? `Approve CAPA ${capaId}?` : `Reject/Reopen CAPA ${capaId}?`;
  if (!confirm(confirmMsg)) return;
  try {
    await patch(`/api/capa/${capaId}`, { status: newStatus });
    loadPage('capa-detail', capaId);
  } catch (err) {
    alert(`Update failed: ${err.message}`);
  }
}
window.submitCapaAction = submitCapaAction;

async function submitCapaStatusUpdate() {
  const capaId = document.getElementById("capa-update-id").value;
  const status = document.getElementById("capa-new-status").value;
  try {
    await patch(`/api/capa/${capaId}`, { status });
    closeModal("capa-status-modal");
    loadCapa();
  } catch (err) {
    alert(`Update failed: ${err.message}`);
  }
}
window.submitCapaStatusUpdate = submitCapaStatusUpdate;

// ── Reports ────────────────────────────────────────────────────────────────
// Recent reports tracker
let _recentReports = [];

async function loadReportSiteSelector() {
  const sel = document.getElementById("report-site-select");
  if (!sel) return;
  try {
    const sites = _allSites.length ? _allSites : await get("/api/sites");
    if (!_allSites.length) _allSites = sites;
    sel.innerHTML = `<option value="">Select a site...</option>` +
      sites.map((s) => `<option value="${s.site_id}">${s.site_id} — ${s.name || s.site_id}</option>`).join("");
  } catch {}
}

function generateSiteReport() {
  const siteId = document.getElementById("report-site-select")?.value;
  if (!siteId) { alert("Please select a site first."); return; }
  generateReport("site", siteId);
}
window.generateSiteReport = generateSiteReport;

function addRecentReport(type, title, siteId) {
  _recentReports.unshift({ type, title, siteId, generated: new Date().toLocaleString() });
  if (_recentReports.length > 10) _recentReports.pop();
  renderRecentReports();
}

function renderRecentReports() {
  const el = document.getElementById("recent-reports-list");
  if (!el) return;
  if (!_recentReports.length) {
    el.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:13px">No reports generated yet. Use the report cards above to generate your first report.</div>`;
    return;
  }
  el.innerHTML = `<table class="data-table">
    <thead><tr><th>Report Name</th><th>Type</th><th>Generated</th><th>Action</th></tr></thead>
    <tbody>${_recentReports.map((r) => `<tr>
      <td>${r.title}</td>
      <td><span class="badge badge-info">${r.type.toUpperCase()}</span></td>
      <td style="font-size:12px;color:var(--text-muted)">${r.generated}</td>
      <td><button class="btn btn-sm btn-ghost" onclick="generateReport('${r.type}','${r.siteId||''}')">View</button></td>
    </tr>`).join('')}</tbody>
  </table>`;
}

async function generateReport(type, siteId) {
  const modal = document.getElementById("report-modal");
  const body = document.getElementById("report-modal-body");
  const title = document.getElementById("report-modal-title");
  body.innerHTML = `<div class="loading-cell"><span class="spinner"></span> Generating report...</div>`;
  modal.style.display = "flex";

  try {
    let data, html = "", titleText = "";
    if (type === "trial") {
      data = await get("/api/reports/trial");
      titleText = "Trial Summary Report";
      html = renderTrialReport(data);
    } else if (type === "deviations") {
      data = await get("/api/reports/deviations");
      titleText = "Deviations Report";
      html = renderDevsReport(data);
    } else if (type === "capa") {
      data = await get("/api/reports/capa");
      titleText = "CAPA Report";
      html = renderCapaReport(data);
    } else if (type === "site") {
      data = await get(`/api/reports/site/${siteId}`);
      titleText = `Site Risk Report — ${siteId}`;
      html = renderSiteReport(data, siteId);
    }
    title.textContent = titleText;
    body.innerHTML = html;
    addRecentReport(type, titleText, siteId);
  } catch (err) {
    body.innerHTML = `<div class="disclaimer-box">Error generating report: ${err.message}</div>`;
  }
}
window.generateReport = generateReport;

function renderTrialReport(data) {
  return `<div class="report-content">
    <div class="report-title">Trial Summary Report — TG-101</div>
    <div class="report-meta">Generated: ${new Date().toLocaleString()} · Generated by: ${_session?.name}</div>
    <div class="report-section"><h4>Overview</h4>
      <div class="detail-row"><span class="detail-label">Total Sites</span><span>${data.total_sites}</span></div>
      <div class="detail-row"><span class="detail-label">Total Deviations</span><span>${data.total_deviations}</span></div>
      <div class="detail-row"><span class="detail-label">Major Deviations</span><span class="risk-score-high">${data.major_deviations}</span></div>
      <div class="detail-row"><span class="detail-label">High-Risk Sites</span><span class="risk-score-high">${(data.high_risk_sites || []).length}</span></div>
      <div class="detail-row"><span class="detail-label">Open CAPAs</span><span>${data.open_capas}</span></div>
    </div>
    <div class="report-section"><h4>High-Risk Sites</h4>
      ${(data.high_risk_sites || []).map((s) => `
        <div class="detail-row">
          <span class="detail-label">${s.site_id}</span>
          <span><span class="badge badge-HIGH">HIGH</span> Score: ${s.current_score}/100 · ${s.trend}</span>
        </div>`).join("")}
    </div>
    <div class="disclaimer-box">${data.disclaimer}</div>
  </div>`;
}

function renderDevsReport(data) {
  const devs = data.deviations || [];
  const major = devs.filter((d) => d.severity === "MAJOR").length;
  return `<div class="report-content">
    <div class="report-title">Protocol Deviations Report</div>
    <div class="report-meta">Generated: ${new Date().toLocaleString()} · Total: ${devs.length} · Major: ${major}</div>
    <div class="report-section"><h4>Deviation Summary</h4>
      <table class="data-table">
        <thead><tr><th>ID</th><th>Site</th><th>Patient</th><th>Type</th><th>Severity</th><th>Detected</th><th>Status</th></tr></thead>
        <tbody>${devs.slice(0, 50).map((d) => `<tr>
          <td>${d.deviation_id}</td><td>${d.site_id}</td><td>${d.patient_id}</td>
          <td>${(d.type || "").replace(/_/g, " ")}</td>
          <td><span class="badge badge-${(d.severity || "").toLowerCase()}">${d.severity}</span></td>
          <td>${d.detected_at}</td>
          <td><span class="badge badge-${d.status}">${d.status}</span></td>
        </tr>`).join("")}</tbody>
      </table>
      ${devs.length > 50 ? `<p class="text-muted" style="margin-top:8px">Showing 50 of ${devs.length} deviations.</p>` : ""}
    </div>
    <div class="disclaimer-box">${data.disclaimer}</div>
  </div>`;
}

function renderCapaReport(data) {
  const records = data.capa_records || [];
  return `<div class="report-content">
    <div class="report-title">CAPA Report</div>
    <div class="report-meta">Generated: ${new Date().toLocaleString()} · Total: ${records.length}</div>
    ${records.map((c) => `
      <div class="report-section">
        <h4>${c.capa_id} — ${c.site_id} — <span class="badge badge-${c.status}">${c.status}</span></h4>
        <div class="detail-row"><span class="detail-label">Problem</span><span>${c.problem_statement}</span></div>
        <div class="detail-row"><span class="detail-label">Priority</span><span>${c.priority}</span></div>
        <div class="detail-row"><span class="detail-label">Owner</span><span>${c.owner}</span></div>
        <div class="detail-row"><span class="detail-label">Due</span><span>${c.due_date || "—"}</span></div>
      </div>`).join("")}
    <div class="disclaimer-box">${data.disclaimer}</div>
  </div>`;
}

function renderSiteReport(data, siteId) {
  const risk = data.risk || {};
  const devs = data.deviations || [];
  return `<div class="report-content">
    <div class="report-title">Site Risk Report — ${siteId}</div>
    <div class="report-meta">Generated: ${new Date().toLocaleString()} · Generated by: ${_session?.name}</div>
    <div class="report-section"><h4>Risk Summary</h4>
      <div class="detail-row"><span class="detail-label">Risk Score</span><span class="risk-score-${(risk.risk_level || "").toLowerCase()}">${risk.current_score}/100</span></div>
      <div class="detail-row"><span class="detail-label">Risk Level</span><span><span class="badge badge-${risk.risk_level}">${risk.risk_level}</span></span></div>
      <div class="detail-row"><span class="detail-label">Trend</span><span><span class="badge badge-${risk.trend}">${risk.trend}</span></span></div>
      <div class="detail-row"><span class="detail-label">Predicted Score</span><span>${risk.predicted_score}/100</span></div>
    </div>
    <div class="report-section"><h4>Leading Indicators</h4>
      ${(risk.leading_indicators || []).map((i) => `<div>• ${i}</div>`).join("")}
    </div>
    <div class="report-section"><h4>Deviations (${devs.length})</h4>
      <table class="data-table">
        <thead><tr><th>ID</th><th>Type</th><th>Severity</th><th>Detected</th></tr></thead>
        <tbody>${devs.slice(0, 30).map((d) => `<tr>
          <td>${d.deviation_id}</td>
          <td>${(d.type || "").replace(/_/g, " ")}</td>
          <td><span class="badge badge-${(d.severity || "").toLowerCase()}">${d.severity}</span></td>
          <td>${d.detected_at}</td>
        </tr>`).join("")}</tbody>
      </table>
    </div>
    <div class="disclaimer-box">${data.disclaimer}</div>
  </div>`;
}

function printReport() {
  window.print();
}
window.printReport = printReport;

// ── Audit ──────────────────────────────────────────────────────────────────
async function loadAudit() {
  try {
    _allAuditEvents = await get("/api/audit");
    // Populate user filter
    const userFilter = document.getElementById("audit-user-filter");
    if (userFilter && _allAuditEvents.length) {
      const users = [...new Set(_allAuditEvents.map((e) => e.user_id))].sort();
      userFilter.innerHTML = `<option value="">All users</option>` + users.map((u) => `<option value="${u}">${u}</option>`).join("");
    }
    renderAuditTable(_allAuditEvents);
    setupAuditFilters();
  } catch (err) {
    document.getElementById("audit-tbody").innerHTML = `<tr><td colspan="6" class="loading-cell">Error: ${err.message}</td></tr>`;
  }
}

function renderAuditTable(events) {
  const fmtDate = (ts) => {
    if (!ts) return "—";
    const d = new Date(ts);
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) + " " + d.toTimeString().slice(0, 8);
  };
  document.getElementById("audit-tbody").innerHTML = events.map((e) => `<tr>
    <td style="font-size:11px;white-space:nowrap">${fmtDate(e.timestamp)}</td>
    <td>${e.user_id}</td>
    <td><span class="audit-action-badge">${e.action}</span></td>
    <td>${e.resource_type}</td>
    <td>${e.resource_id || "—"}</td>
    <td style="font-size:11px;color:var(--text-muted)">${Object.keys(e.metadata || {}).length ? JSON.stringify(e.metadata) : "—"}</td>
  </tr>`).join("") || `<tr><td colspan="6" class="loading-cell">No events.</td></tr>`;
}

function setupAuditFilters() {
  const search = document.getElementById("audit-search");
  const actionFilter = document.getElementById("audit-action-filter");
  const userFilter = document.getElementById("audit-user-filter");

  const applyAuditFilters = () => {
    const q = (search?.value || "").toLowerCase();
    const action = actionFilter?.value || "";
    const user = userFilter?.value || "";
    const filtered = _allAuditEvents.filter((e) => {
      const matchQ = !q || e.user_id.toLowerCase().includes(q) || e.action.toLowerCase().includes(q) || (e.resource_id || "").toLowerCase().includes(q) || e.resource_type.toLowerCase().includes(q);
      const matchAction = !action || e.action === action;
      const matchUser = !user || e.user_id === user;
      return matchQ && matchAction && matchUser;
    });
    renderAuditTable(filtered);
  };

  if (search) search.addEventListener("input", applyAuditFilters);
  if (actionFilter) actionFilter.addEventListener("change", applyAuditFilters);
  if (userFilter) userFilter.addEventListener("change", applyAuditFilters);
}

// ── IBM Bob ────────────────────────────────────────────────────────────────
async function loadBobTools() {
  try {
    const tools = await get("/api/bob/tools");
    document.getElementById("bob-tools-list").innerHTML = tools.map((t) => `
      <div class="tool-item">
        <span class="tool-name">${t.tool_name}</span>
        ${t.description}
      </div>
    `).join("");
    const providerEl = document.getElementById("bob-provider-name");
    if (providerEl) providerEl.textContent = "Demo Adapter (MCP-ready boundary)";
  } catch {}
}

function setupBobInput() {
  const input = document.getElementById("bob-input");
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendBobMessage();
      }
    });
  }
}

async function sendBobMessage() {
  const input = document.getElementById("bob-input");
  const question = input.value.trim();
  if (!question) return;
  input.value = "";
  await askBob(question);
}
window.sendBobMessage = sendBobMessage;

async function askBob(question) {
  // Switch to Bob page if not already there
  const bobPage = document.getElementById("page-bob");
  if (!bobPage.classList.contains("active")) {
    loadPage("bob");
    await new Promise((r) => setTimeout(r, 200));
  }

  const messages = document.getElementById("bob-messages");

  // Add user message
  messages.insertAdjacentHTML("beforeend", `
    <div class="bob-message user-message">
      <div class="user-avatar-msg">${(_session?.name || "U")[0]}</div>
      <div class="user-msg-content">${escapeHtml(question)}</div>
    </div>
  `);

  // Add thinking message
  const thinkingId = `thinking-${Date.now()}`;
  messages.insertAdjacentHTML("beforeend", `
    <div class="bob-message bot-message thinking-msg" id="${thinkingId}">
      <div class="bot-avatar">B</div>
      <div class="message-content">TrialGuard Demo Assistant is querying tools...</div>
    </div>
  `);
  messages.scrollTop = messages.scrollHeight;

  try {
    const result = await post("/api/bob/ask", { question });
    document.getElementById(thinkingId)?.remove();

    const answer = result.answer || "No response.";
    const sources = result.sources || [];
    const provider = result.provider || "";
    const toolUsed = result.tool_used || "";
    const disclaimer = result.disclaimer || "";

    messages.insertAdjacentHTML("beforeend", `
      <div class="bob-message bot-message">
        <div class="bot-avatar">B</div>
        <div class="message-content">
          <p style="white-space:pre-line">${escapeHtml(answer)}</p>
          <div class="message-sources">
            ${sources.map((s) => `<span class="source-chip">${escapeHtml(s)}</span>`).join("")}
            ${toolUsed ? `<span class="source-chip">${escapeHtml(toolUsed)}</span>` : ""}
            ${provider ? `<span class="provider-chip">${escapeHtml(provider)}</span>` : ""}
          </div>
          ${disclaimer ? `<div style="margin-top:8px;font-size:11px;color:var(--text-muted);font-style:italic">⚠ ${escapeHtml(disclaimer)}</div>` : ""}
          ${result.tool_used && result.tool_result ? `
            <div class="bob-evidence-panel">
              <button class="bob-evidence-toggle" onclick="this.nextElementSibling.classList.toggle('open');this.textContent=this.nextElementSibling.classList.contains('open')?'▲ Hide Investigation Evidence':'▼ Show Investigation Evidence'">▼ Show Investigation Evidence</button>
              <div class="bob-evidence-content">
                <div class="evidence-row"><span class="evidence-label">Tool used:</span><span class="evidence-val">${escapeHtml(toolUsed)}</span></div>
                <div class="evidence-row"><span class="evidence-label">Provider:</span><span class="evidence-val">${escapeHtml(provider)}</span></div>
                <div class="evidence-row"><span class="evidence-label">Data source:</span><span class="evidence-val">TrialGuard application database</span></div>
                <div class="evidence-tools">
                  ${toolUsed ? `<span class="evidence-tool-chip">${escapeHtml(toolUsed)}</span>` : ""}
                </div>
              </div>
            </div>
          ` : ""}
        </div>
      </div>
    `);
    messages.scrollTop = messages.scrollHeight;
  } catch (err) {
    document.getElementById(thinkingId)?.remove();
    messages.insertAdjacentHTML("beforeend", `
      <div class="bob-message bot-message">
        <div class="bot-avatar">B</div>
        <div class="message-content" style="color:var(--risk-high)">Error: ${escapeHtml(err.message || "Request failed")}</div>
      </div>
    `);
  }
}
window.askBob = askBob;

// ── Settings ───────────────────────────────────────────────────────────────
async function loadSettings() {
  if (_session?.role !== "SYSTEM_ADMIN") return;
  try {
    const users = await get("/api/users");
    document.getElementById("users-list").innerHTML = users.map((u) => `
      <div class="user-row">
        <div class="user-avatar" style="width:28px;height:28px;font-size:12px">${u.name[0]}</div>
        <div style="flex:1">
          <div style="font-size:13px;font-weight:600">${u.name}</div>
          <div style="font-size:11px;color:var(--text-muted)">${u.email}</div>
        </div>
        <span class="demo-role-badge role-${u.role}" style="font-size:10px">${u.role.replace("_", " ")}</span>
      </div>
    `).join("");
  } catch {}
}

async function recalculateRisk() {
  try {
    const result = await post("/api/risk/recalculate", {});
    document.getElementById("recalc-status").innerHTML = `<div class="badge badge-success">✓ Recalculated ${result.sites} sites</div>`;
  } catch (err) {
    document.getElementById("recalc-status").innerHTML = `<div class="badge badge-major">Error: ${err.message}</div>`;
  }
}
window.recalculateRisk = recalculateRisk;

// ── Modals ─────────────────────────────────────────────────────────────────
function closeModal(id) {
  document.getElementById(id).style.display = "none";
}
window.closeModal = closeModal;

// Close modals on overlay click
document.querySelectorAll(".modal-overlay").forEach((overlay) => {
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.style.display = "none";
  });
});

// ── Utilities ──────────────────────────────────────────────────────────────
function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}


// ── Page Context ────────────────────────────────────────────────────────────
function setPageContext(type, id, label) {
  _currentContext = type ? { type, id, label } : null;
  const tooltip = document.getElementById("bob-context-tooltip");
  if (tooltip) {
    if (_currentContext) {
      tooltip.textContent = "Context: " + _currentContext.label;
      tooltip.style.display = "block";
    } else {
      tooltip.style.display = "none";
    }
  }
}
window.setPageContext = setPageContext;

// ── Dashboard Attention ─────────────────────────────────────────────────────
async function loadDashboardAttention() {
  try {
    const data = await get("/api/dashboard/attention");

    // Trial Health Indicator
    const scoreEl = document.getElementById("th-score");
    const levelEl = document.getElementById("th-level");
    const trendEl = document.getElementById("th-trend");
    if (scoreEl) {
      const score = data.trial_health_score || 0;
      const riskScore = 100 - score; // convert health to risk
      scoreEl.textContent = riskScore;
      const level = data.health_level || "STABLE";
      levelEl.textContent = level;
      levelEl.className = "th-level th-level-" + level.toLowerCase();
      const worsening = (data.attention_sites || []).filter((s) => s.trend === "WORSENING").length;
      trendEl.textContent = worsening > 0 ? `↑ ${worsening} site(s) WORSENING` : "→ STABLE";
      scoreEl.style.color = riskScore >= 65 ? "var(--risk-high)" : riskScore >= 35 ? "var(--risk-medium)" : "var(--risk-low)";
    }

    // What Needs Attention
    const attItems = document.getElementById("attention-items");
    if (attItems) {
      const sites = data.attention_sites || [];
      if (!sites.length) {
        attItems.innerHTML = '<div style="font-size:12px;color:var(--text-muted);padding:8px 0">No high-risk sites requiring immediate attention.</div>';
      } else {
        attItems.innerHTML = sites.map((s) => {
          const dotClass = s.risk_level === "HIGH" ? "high" : s.risk_level === "MEDIUM" ? "medium" : "low";
          return `<div class="attention-item">
            <div class="attention-dot ${dotClass}"></div>
            <div style="flex:1;min-width:0">
              <div class="attention-site">${s.site_id}</div>
              <div class="attention-detail">Risk ${s.current_score} → Projected ${s.predicted_score} · ${s.trend}</div>
            </div>
            <div class="attention-actions">
              <button class="btn btn-sm btn-primary" onclick="loadPage('site-detail','${s.site_id}')">Investigate</button>
            </div>
          </div>`;
        }).join("");
      }
    }

    // Early Warning Center
    const ewItems = document.getElementById("ew-items");
    if (ewItems) {
      const warnings = data.early_warnings || [];
      if (!warnings.length) {
        ewItems.innerHTML = '<div style="font-size:12px;color:var(--text-muted);padding:8px 0">No active early warnings.</div>';
      } else {
        ewItems.innerHTML = warnings.map((w) => {
          const indHtml = (w.leading_indicators || []).slice(0, 3).map((i) => `<span class="ew-indicator">${escapeHtml(i)}</span>`).join("");
          const riskChangeHtml = w.risk_change !== undefined && w.risk_change !== 0
            ? `<span style="color:${w.risk_change > 0 ? 'var(--risk-high)' : 'var(--risk-low)'}; font-size:11px; font-weight:600; margin-left:6px">
                ${w.risk_change > 0 ? '↑' : '↓'}${Math.abs(w.risk_change)}pts
               </span>`
            : "";
          const primarySignalHtml = w.primary_signal
            ? `<div style="font-size:11px;font-weight:600;color:var(--risk-high);margin-bottom:3px">⚠ ${escapeHtml(w.primary_signal)}</div>`
            : "";
          const recentHtml = w.recent_deviation_count !== undefined
            ? `<span class="ew-indicator">${w.recent_deviation_count} recent</span>`
            : "";
          return `<div class="ew-item">
            <div class="ew-item-site">${w.site_id}</div>
            ${primarySignalHtml}
            <div class="ew-item-scores">Risk: ${w.current_score}/100 → Projected: ${w.predicted_score}/100${riskChangeHtml}</div>
            <div class="ew-item-indicators">${indHtml}${recentHtml}</div>
            <div class="ew-actions">
              <button class="btn btn-sm btn-primary" onclick="loadPage('site-detail','${w.site_id}')">Investigate</button>
              <button class="btn btn-sm btn-secondary" onclick="loadPage('bob');setTimeout(()=>askBob('Why is Site ${w.site_id} high risk?'),200)">Ask Bob</button>
            </div>
          </div>`;
        }).join("");
      }
    }
  } catch (err) {
    console.error("Attention panel failed:", err);
  }
}

// ── Site Heatmap ────────────────────────────────────────────────────────────
let _hmSites = [];      // full dataset cached for re-sort
let _hmSort  = "risk";  // current sort key

function _hmRiskBand(score) {
  if (score >= 90) return "critical";
  if (score >= 80) return "high";
  if (score >= 60) return "elevated";
  if (score >= 30) return "moderate";
  return "low";
}

function _hmBandLabel(score) {
  if (score >= 90) return "CRITICAL";
  if (score >= 80) return "HIGH";
  if (score >= 60) return "ELEVATED";
  if (score >= 30) return "MODERATE";
  return "LOW";
}

function _hmSorted(sites, key) {
  const copy = [...sites];
  if (key === "risk")  return copy.sort((a, b) => b.risk_score - a.risk_score);
  if (key === "id")    return copy.sort((a, b) => a.site_id.localeCompare(b.site_id));
  if (key === "trend") {
    const order = { WORSENING: 0, STABLE: 1, IMPROVING: 2 };
    return copy.sort((a, b) => {
      const diff = (order[a.trend] ?? 1) - (order[b.trend] ?? 1);
      return diff !== 0 ? diff : b.risk_score - a.risk_score;
    });
  }
  return copy;
}

function _hmTrendIcon(trend) {
  if (trend === "WORSENING") return '<span class="hm-trend hm-trend-worse">↑ WORSENING</span>';
  if (trend === "IMPROVING") return '<span class="hm-trend hm-trend-better">↓ IMPROVING</span>';
  return "";
}

function _renderHeatmapTiles(sites) {
  const container = document.getElementById("site-heatmap");
  if (!container) return;
  const tooltip  = document.getElementById("hm-tooltip");

  container.innerHTML = _hmSorted(sites, _hmSort).map((s, idx) => {
    const band      = _hmRiskBand(s.risk_score);
    const label     = _hmBandLabel(s.risk_score);
    const trendHtml = _hmTrendIcon(s.trend);
    const isBlack   = s.is_blacklisted;
    const isCrit    = s.risk_score >= 90;

    return `<div
      class="hm-tile hm-band-${band}${isBlack ? " hm-blacklisted" : ""}${isCrit && !isBlack ? " hm-near-critical" : ""}"
      data-idx="${idx}"
      onclick="loadPage('site-detail','${escapeHtml(s.site_id)}')"
      role="button"
      tabindex="0"
      aria-label="${escapeHtml(s.name || s.site_id)}, risk score ${s.risk_score}, ${label}"
      style="animation-delay:${Math.min(idx * 18, 400)}ms"
    >
      <div class="hm-tile-top">
        <span class="hm-tile-id">${escapeHtml(s.site_id)}</span>
        ${isBlack
          ? '<span class="hm-tile-status-icon hm-icon-blacklisted" title="Blacklisted"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M6 1 L11 10 H1 Z"/><line x1="6" y1="5" x2="6" y2="7.5"/><circle cx="6" cy="9" r="0.6" fill="currentColor" stroke="none"/></svg></span>'
          : isCrit
            ? '<span class="hm-tile-status-icon hm-icon-critical" title="Critical risk"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="6" cy="6" r="5"/><line x1="6" y1="4" x2="6" y2="6.5"/><circle cx="6" cy="8.5" r="0.6" fill="currentColor" stroke="none"/></svg></span>'
            : ""
        }
      </div>
      <div class="hm-tile-score">${s.risk_score}</div>
      <div class="hm-tile-label">${label}</div>
      ${trendHtml}
      ${isBlack ? '<div class="hm-tile-blacklisted-badge">BLACKLISTED</div>' : ""}
    </div>`;
  }).join("");

  // Keyboard navigation
  container.querySelectorAll(".hm-tile").forEach((tile) => {
    tile.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); tile.click(); }
    });
  });

  // Tooltip
  if (tooltip) {
    const sorted = _hmSorted(sites, _hmSort);
    container.querySelectorAll(".hm-tile").forEach((tile) => {
      const idx = parseInt(tile.dataset.idx, 10);
      const s   = sorted[idx];
      if (!s) return;

      tile.addEventListener("mouseenter", (e) => {
        const band  = _hmBandLabel(s.risk_score);
        const trendLabel = s.trend === "WORSENING" ? "↑ Worsening"
                         : s.trend === "IMPROVING" ? "↓ Improving"
                         : "→ Stable";
        tooltip.innerHTML = `
          <div class="hm-tt-title">${escapeHtml(s.name || s.site_id)}</div>
          <div class="hm-tt-grid">
            <span class="hm-tt-key">Risk Score</span><span class="hm-tt-val hm-tt-score">${s.risk_score} / 100</span>
            <span class="hm-tt-key">Status</span><span class="hm-tt-val">${band}</span>
            <span class="hm-tt-key">Trend</span><span class="hm-tt-val">${trendLabel}</span>
            ${s.location ? `<span class="hm-tt-key">Location</span><span class="hm-tt-val">${escapeHtml(s.location)}</span>` : ""}
            ${s.is_blacklisted ? `<span class="hm-tt-key">Blacklist</span><span class="hm-tt-val hm-tt-blacklist">BLACKLISTED</span>` : ""}
          </div>
          <div class="hm-tt-footer">Click to investigate →</div>
        `;
        tooltip.style.display = "block";
        _positionHmTooltip(e, tooltip);
      });
      tile.addEventListener("mousemove", (e) => _positionHmTooltip(e, tooltip));
      tile.addEventListener("mouseleave", () => { tooltip.style.display = "none"; });
    });
  }
}

function _positionHmTooltip(e, tooltip) {
  const panel = tooltip.closest(".hm-panel") || document.body;
  const pr    = panel.getBoundingClientRect();
  const tw    = tooltip.offsetWidth  || 220;
  const th    = tooltip.offsetHeight || 120;
  let   x     = e.clientX - pr.left + 14;
  let   y     = e.clientY - pr.top  - th / 2;
  if (x + tw > pr.width  - 8) x = e.clientX - pr.left - tw - 14;
  if (y < 4)                   y = 4;
  if (y + th > pr.height - 4)  y = pr.height - th - 4;
  tooltip.style.left = x + "px";
  tooltip.style.top  = y + "px";
}

function setHeatmapSort(key) {
  _hmSort = key;
  document.querySelectorAll(".hm-sort-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.sort === key);
  });
  _renderHeatmapTiles(_hmSites);
}

async function loadSiteHeatmap() {
  try {
    const sites = await get("/api/dashboard/heatmap");
    const container = document.getElementById("site-heatmap");
    if (!container) return;
    if (!sites || !sites.length) {
      container.innerHTML = '<div class="state-empty">No site data available.</div>';
      return;
    }
    _hmSites = sites;
    const countEl = document.getElementById("hm-site-count");
    if (countEl) countEl.textContent = `${sites.length} site${sites.length !== 1 ? "s" : ""}`;
    _renderHeatmapTiles(sites);
  } catch (err) {
    console.error("Heatmap failed:", err);
  }
}

// ── Sites Becoming Risky (P0-8) ─────────────────────────────────────────────
async function loadEmergingSites() {
  try {
    const data = await get("/api/dashboard/emerging-sites");
    const container = document.getElementById("emerging-sites-container");
    if (!container) return;
    const sites = data.emerging_sites || [];
    if (!sites.length) {
      container.style.display = "none";
      return;
    }
    container.style.display = "block";
    container.innerHTML = `
      <div class="data-panel">
        <div class="panel-header">
          <h3>Sites Becoming Risky</h3>
          <span style="font-size:12px;color:var(--text-muted)">Top sites by risk acceleration this period</span>
        </div>
        <div class="table-container">
          <table class="data-table">
            <thead><tr>
              <th>Site</th><th>Previous</th><th>Current</th><th>Change</th><th>Projected</th><th>Primary Signal</th><th>Action</th>
            </tr></thead>
            <tbody>
              ${sites.map(s => `<tr>
                <td><button class="btn btn-sm btn-ghost" onclick="loadPage('site-detail','${s.site_id}')">${s.site_id}</button></td>
                <td>${s.previous_score}/100</td>
                <td><strong style="color:${s.current_score >= 65 ? 'var(--risk-high)' : s.current_score >= 35 ? 'var(--risk-medium)' : 'var(--risk-low)'}">${s.current_score}/100</strong></td>
                <td style="color:var(--risk-high);font-weight:600">↑ +${s.risk_change}</td>
                <td>${s.projected_score}/100</td>
                <td style="font-size:12px;color:var(--text-muted)">${escapeHtml(s.primary_signal || '—')}</td>
                <td><button class="btn btn-sm btn-primary" onclick="loadPage('site-detail','${s.site_id}')">Investigate</button></td>
              </tr>`).join("")}
            </tbody>
          </table>
        </div>
        <div class="disclaimer-box" style="margin-top:8px">⚠ Risk acceleration calculated from deterministic synthetic data. Not for clinical use.</div>
      </div>
    `;
  } catch (err) {
    console.error("Emerging sites failed:", err);
  }
}

// ── Notifications ───────────────────────────────────────────────────────────
async function loadNotifications() {
  try {
    _notifications = await get("/api/notifications");
    const badge = document.getElementById("notif-count");
    if (badge) {
      const count = _notifications.filter((n) => n.level === "high").length;
      if (count > 0) {
        badge.textContent = count;
        badge.style.display = "flex";
      }
    }
    renderNotificationsPanel();
  } catch (err) {
    console.error("Notifications failed:", err);
  }
}

function renderNotificationsPanel() {
  const list = document.getElementById("notif-panel-list");
  if (!list) return;
  if (!_notifications.length) {
    list.innerHTML = '<div class="notif-empty">No notifications.</div>';
    return;
  }
  list.innerHTML = _notifications.map((n) => `
    <div class="notif-item" onclick="handleNotifClick('${escapeHtml(n.link_page || "")}','${escapeHtml(n.resource_id || n.site_id || "")}')">
      <div class="notif-dot ${n.level}"></div>
      <div style="flex:1;min-width:0">
        <div class="notif-title">${escapeHtml(n.title)}</div>
        <div class="notif-msg">${escapeHtml(n.message)}</div>
      </div>
    </div>
  `).join("");
}

function handleNotifClick(page, id) {
  const panel = document.getElementById("notifications-panel");
  if (panel) panel.style.display = "none";
  if (page && id) loadPage(page, id);
  else if (page) loadPage(page);
}
window.handleNotifClick = handleNotifClick;

// ── Global Search ───────────────────────────────────────────────────────────
function setupGlobalSearch() {
  const input = document.getElementById("global-search");
  if (!input) return;
  let searchTimeout;
  input.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    const q = input.value.trim();
    if (q.length < 2) {
      document.getElementById("global-search-results").style.display = "none";
      return;
    }
    searchTimeout = setTimeout(() => performSearch(q), 300);
  });
  input.addEventListener("focus", () => {
    if (input.value.trim().length >= 2) performSearch(input.value.trim());
  });
  input.addEventListener("click", (e) => e.stopPropagation());
}

async function performSearch(q) {
  try {
    const data = await get(`/api/search?q=${encodeURIComponent(q)}`);
    renderSearchResults(data, q);
  } catch (err) {
    console.error("Search failed:", err);
  }
}

function renderSearchResults(data, q) {
  const container = document.getElementById("global-search-results");
  if (!container) return;
  const categories = [
    { key: "sites", label: "Sites", page: "site-detail" },
    { key: "deviations", label: "Deviations", page: "deviation-detail" },
    { key: "capas", label: "CAPA Records", page: "capa-detail" },
    { key: "patients", label: "Patients", page: null },
    { key: "rules", label: "Protocol Rules", page: null },
  ];
  let html = "";
  let total = 0;
  for (const cat of categories) {
    const items = data[cat.key] || [];
    if (!items.length) continue;
    total += items.length;
    html += `<div class="search-category">${cat.label}</div>`;
    html += items.map((item) => `
      <div class="search-result-item" onclick="handleSearchClick('${cat.page || ""}','${escapeHtml(String(item.id))}')">
        <div style="flex:1;min-width:0">
          <div class="search-result-label">${escapeHtml(item.label)}</div>
          ${item.sublabel ? `<div class="search-result-sub">${escapeHtml(item.sublabel)}</div>` : ""}
        </div>
        <span class="search-result-type">${cat.key.slice(0, -1)}</span>
      </div>
    `).join("");
  }
  if (!total) {
    html = `<div class="search-no-results">No results found for "${escapeHtml(q)}"</div>`;
  }
  container.innerHTML = html;
  container.style.display = "block";
}

function handleSearchClick(page, id) {
  const input = document.getElementById("global-search");
  if (input) input.value = "";
  const results = document.getElementById("global-search-results");
  if (results) results.style.display = "none";
  if (page) loadPage(page, id);
}
window.handleSearchClick = handleSearchClick;

// ── Investigate Site With Bob ───────────────────────────────────────────────
async function investigateSiteWithBob(siteId) {
  loadPage("bob");
  await new Promise((r) => setTimeout(r, 200));

  const messages = document.getElementById("bob-messages");

  messages.insertAdjacentHTML("beforeend", `
    <div class="bob-message bot-message">
      <div class="bot-avatar">B</div>
      <div class="message-content">
        <div class="investigate-panel" id="invest-panel-${siteId}">
          <div class="investigate-header">Investigating Site ${siteId}...</div>
          <div class="investigate-steps" id="invest-steps-${siteId}">
            ${["Retrieve current risk", "Analyze risk drivers", "Retrieve recent deviations", "Analyze trend", "Identify leading indicators", "Recommend actions"].map((s, i) => `
              <div class="investigate-step pending" id="invest-step-${siteId}-${i}">
                <span class="step-icon">○</span>
                <span class="step-text">${s}</span>
                <span class="step-status">Pending</span>
              </div>
            `).join("")}
          </div>
          <div class="investigate-result" id="invest-result-${siteId}" style="display:none"></div>
        </div>
      </div>
    </div>
  `);
  messages.scrollTop = messages.scrollHeight;

  const setStep = (i, state, status) => {
    const step = document.getElementById(`invest-step-${siteId}-${i}`);
    if (!step) return;
    step.className = `investigate-step ${state}`;
    step.querySelector(".step-icon").textContent = state === "done" ? "✓" : state === "active" ? "◉" : "○";
    step.querySelector(".step-status").textContent = status;
  };

  try {
    setStep(0, "active", "Running...");
    const riskResult = await post("/api/bob/ask", { question: `What is the current risk for Site ${siteId}?` });
    setStep(0, "done", "Done");

    setStep(1, "active", "Running...");
    const explainResult = await post("/api/bob/ask", { question: `Why is Site ${siteId} high risk?` });
    setStep(1, "done", "Done");

    setStep(2, "active", "Running...");
    await post("/api/bob/ask", { question: `Show major deviations at Site ${siteId}` });
    setStep(2, "done", "Done");

    setStep(3, "active", "Running...");
    await post("/api/bob/ask", { question: `Show trend for Site ${siteId}` });
    setStep(3, "done", "Done");

    setStep(4, "active", "Running...");
    await new Promise((r) => setTimeout(r, 300));
    setStep(4, "done", "Done");

    setStep(5, "active", "Running...");
    await post("/api/bob/ask", { question: `Recommend actions for Site ${siteId}` });
    setStep(5, "done", "Done");

    const resultEl = document.getElementById(`invest-result-${siteId}`);
    if (resultEl) {
      resultEl.style.display = "block";
      resultEl.innerHTML = `
        <h4 style="margin-bottom:12px">Investigation Complete — Site ${siteId}</h4>
        <p style="white-space:pre-line;font-size:13px">${escapeHtml(explainResult.answer || "")}</p>
        <div style="margin-top:10px">
          <button class="btn btn-sm btn-primary" onclick="loadPage('site-detail','${siteId}')">View Site Detail</button>
          <button class="btn btn-sm btn-secondary" onclick="openCapaModalForSite('${siteId}')">Generate CAPA</button>
        </div>
      `;
    }
    messages.scrollTop = messages.scrollHeight;
  } catch (err) {
    const resultEl = document.getElementById(`invest-result-${siteId}`);
    if (resultEl) {
      resultEl.style.display = "block";
      resultEl.innerHTML = `<div style="color:var(--risk-high)">Investigation failed: ${escapeHtml(err.message || "Unknown error")}</div>`;
    }
  }
}
window.investigateSiteWithBob = investigateSiteWithBob;


// ── Bootstrap ──────────────────────────────────────────────────────────────
// If token exists, try to auto-login by checking session
(async function init() {
  const token = localStorage.getItem("tg_token");
  if (token) {
    try {
      // Try a protected endpoint to check if session is still valid
      const summary = await get("/api/dashboard/summary");
      // If we get here, we need to reconstruct the session from storage
      // We'll do a quick user fetch — but we don't have user info, so just hide login and load
      // The server enforces auth on every request; if it passes, we're good
      // We need a way to get the current user — try the users list if admin, else just proceed
      // Simplest: just show login again to ensure clean state
      localStorage.removeItem("tg_token");
    } catch {}
  }
  document.getElementById("login-screen").style.display = "flex";
  document.getElementById("app").style.display = "none";
})();

// ── Protocol Patient Compare ────────────────────────────────────────────────
function showPatientCompare(ruleId, ruleName, ruleExpected) {
  const container = document.getElementById(`patient-compare-${ruleId}`);
  if (!container) return;

  // Toggle if already open with input
  if (container.style.display !== "none") {
    container.style.display = "none";
    return;
  }

  container.style.display = "block";
  container.innerHTML = `
    <div class="patient-compare-panel">
      <div style="font-size:11px;font-weight:700;color:var(--text-muted);margin-bottom:10px;text-transform:uppercase;letter-spacing:0.06em">PATIENT COMPLIANCE CHECK — ${escapeHtml(ruleName)}</div>
      <div style="display:flex;gap:8px;margin-bottom:10px">
        <input type="text" id="pc-input-${ruleId}" class="search-input" placeholder="Patient ID (e.g. P-037-019)" style="flex:1">
        <button class="btn btn-primary btn-sm" onclick="runPatientCompare('${ruleId}','${escapeHtml(ruleExpected)}')">Check</button>
      </div>
      <div id="pc-result-${ruleId}"></div>
    </div>
  `;
}
window.showPatientCompare = showPatientCompare;

async function runPatientCompare(ruleId, ruleExpected) {
  const input = document.getElementById(`pc-input-${ruleId}`);
  const resultEl = document.getElementById(`pc-result-${ruleId}`);
  if (!input || !resultEl) return;
  const patientId = input.value.trim();
  if (!patientId) { resultEl.innerHTML = `<div style="color:var(--risk-high);font-size:12px">Please enter a patient ID.</div>`; return; }
  resultEl.innerHTML = `<div class="loading-cell" style="padding:8px;font-size:12px"><span class="spinner"></span> Checking...</div>`;
  try {
    const result = await post("/api/bob/tool", { tool_name: "compare_patient_to_protocol", params: { patient_id: patientId } });
    const compliant = result.compliant;
    const issues = result.issues || [];
    resultEl.innerHTML = `
      <div class="compare-result-row">
        <span class="compare-label">Patient:</span>
        <span class="compare-val">${escapeHtml(patientId)}</span>
      </div>
      <div class="compare-result-row">
        <span class="compare-label">Expected:</span>
        <span class="compare-val">${escapeHtml(ruleExpected)}</span>
      </div>
      <div class="compare-result-row">
        <span class="compare-label">Result:</span>
        <span class="${compliant ? 'compare-status-compliant' : 'compare-status-non-compliant'}">${compliant ? '✓ COMPLIANT' : '✗ NON-COMPLIANT'}</span>
      </div>
      ${issues.length ? `<div style="margin-top:8px">${issues.map(i => `
        <div style="font-size:11px;padding:4px 0;border-bottom:1px solid var(--border)">
          <span style="color:var(--risk-high);font-weight:600">${escapeHtml(i.rule)}</span>: ${escapeHtml(i.finding)}
          <span class="badge badge-${(i.severity||'').toLowerCase()}" style="margin-left:6px">${i.severity}</span>
        </div>`).join('')}</div>` : ''}
      <div style="margin-top:10px;display:flex;gap:6px">
        ${!compliant ? `<button class="btn btn-sm btn-ghost" onclick="loadPage('bob');setTimeout(()=>askBob('Check patient ${escapeHtml(patientId)} against protocol'),200)">Ask Bob</button>` : ''}
        <button class="btn btn-sm btn-ghost" onclick="loadPage('deviations')">View Deviations</button>
      </div>
    `;
  } catch (err) {
    resultEl.innerHTML = `<div style="color:var(--risk-high);font-size:12px">Error: ${escapeHtml(err.message || 'Check failed')}</div>`;
  }
}
window.runPatientCompare = runPatientCompare;

// ── CAPA Approval Workflow ──────────────────────────────────────────────────
function openCapaApprovalModal(capaId, currentStatus) {
  const canApprove = ["STUDY_MANAGER", "SYSTEM_ADMIN"].includes(_session?.role);
  if (!canApprove) { alert("Only Study Managers and Admins can approve or reject CAPAs."); return; }
  document.getElementById("capa-update-id").value = capaId;
  document.getElementById("capa-new-status").value = currentStatus;
  document.getElementById("capa-status-modal").style.display = "flex";
}
window.openCapaApprovalModal = openCapaApprovalModal;

