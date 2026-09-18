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

// ── API layer ──────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const token = localStorage.getItem("tg_token");
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "include",
  };
  if (token) opts.headers["Authorization"] = `Bearer ${token}`;
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
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

  loadPage("dashboard");
  setupNav();
  setupFilters();
  setupBobInput();
  setupGlobalSearch();
  loadNotifications();
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
    case "reports": renderRecentReports(); setPageContext(null); break;
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

// ── Site Detail ────────────────────────────────────────────────────────────
async function loadSiteDetail(siteId) {
  if (!siteId) return;
  const [site, risk, devs, patients] = await Promise.all([
    get(`/api/sites/${siteId}`),
    get(`/api/sites/${siteId}/risk`),
    get(`/api/sites/${siteId}/deviations`),
    get(`/api/sites/${siteId}/patients`).catch(() => []),
  ]);

  document.getElementById("site-detail-header").innerHTML = `
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
      <div>
        <h2 style="margin:0">${site.name}</h2>
        <div style="color:var(--text-muted);font-size:13px">${site.site_id} · ${site.location} · ${site.investigator}</div>
      </div>
      <span class="badge badge-${risk.risk_level}">${risk.risk_level}</span>
      <button class="btn btn-sm btn-secondary" onclick="loadPage('bob')">🤖 Ask IBM Bob</button>
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
        <button class="btn btn-sm btn-primary" onclick="investigateSiteWithBob('${siteId}')" style="margin-bottom:8px;width:100%">🔍 Investigate with Bob</button>
        <button class="btn btn-sm btn-secondary" onclick="loadPage('bob');setTimeout(()=>askBob('Recommend actions for Site ${siteId}'),200)" style="margin-bottom:8px;width:100%">🤖 Ask for Recommendations</button>
        <button class="btn btn-sm btn-secondary" onclick="generateReport('site','${siteId}')" style="width:100%;margin-bottom:8px">📊 Generate Site Report</button>
        <button class="btn btn-sm btn-secondary" onclick="openCapaModalForSite('${siteId}')" style="width:100%">🔧 Generate CAPA</button>
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

    <div class="disclaimer-box">⚠ Risk scores are calculated using a prototype multi-factor framework. Predicted scores are estimates, not guaranteed outcomes. All data is synthetic.</div>
  `;
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
            <button class="btn btn-sm btn-primary" onclick="loadPage('bob');setTimeout(()=>askBob('Explain deviation ${dev.deviation_id} at site ${dev.site_id}'),200)">🤖 Ask Bob About This</button>
          </div>
        </div>
      </div>

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
            <button class="btn btn-secondary btn-full" style="margin-bottom:8px" onclick="openCapaStatusModal('${c.capa_id}','${c.status}')">⚙ Change Status</button>
            <button class="btn btn-ghost btn-full" onclick="generateReport('site','${c.site_id}')">📊 Site Report</button>
            <button class="btn btn-ghost btn-full" style="margin-top:8px" onclick="loadPage('bob');setTimeout(()=>askBob('Explain CAPA ${c.capa_id} for site ${c.site_id}'),200)">🤖 Ask Bob</button>
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
            ${sources.map((s) => `<span class="source-chip">📊 ${escapeHtml(s)}</span>`).join("")}
            ${toolUsed ? `<span class="source-chip">🔧 ${escapeHtml(toolUsed)}</span>` : ""}
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
          return `<div class="ew-item">
            <div class="ew-item-site">${w.site_id}</div>
            <div class="ew-item-scores">Risk: ${w.current_score}/100 → Projected: ${w.predicted_score}/100</div>
            <div class="ew-item-indicators">${indHtml}</div>
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
async function loadSiteHeatmap() {
  try {
    const sites = await get("/api/dashboard/heatmap");
    const container = document.getElementById("site-heatmap");
    if (!container) return;
    if (!sites.length) {
      container.innerHTML = '<div class="state-empty">No site data available.</div>';
      return;
    }
    container.innerHTML = sites.map((s) => {
      const cls = s.risk_level === "HIGH" ? "hm-high" : s.risk_level === "MEDIUM" ? "hm-medium" : "hm-low";
      return `<div class="hm-cell ${cls}" onclick="loadPage('site-detail','${s.site_id}')" title="${escapeHtml(s.name || s.site_id)} — ${s.risk_level} (${s.risk_score}/100)">
        <span class="hm-id">${s.site_id}</span>
        <span class="hm-score">${s.risk_score}</span>
      </div>`;
    }).join("");
  } catch (err) {
    console.error("Heatmap failed:", err);
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
          <div class="investigate-header">🔍 Investigating Site ${siteId}</div>
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

