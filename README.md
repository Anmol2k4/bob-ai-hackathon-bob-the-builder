# TrialGuard AI — Clinical Trial Risk Monitor & Protocol Deviation Detector

> **IBM Bobathon 2026 · Bob the Builder team · AI track**

TrialGuard AI helps clinical-trial risk managers detect protocol deviations early, predict which sites are becoming risky, explain why risk is rising, and generate CAPA-ready action plans — all before the audit.

**Core product promise:**
> "Don't wait for the audit. Detect deviations early, predict site risk, explain the cause, and generate the action plan."

---

## Team

| Role | Name | Contact |
|---|---|---|
| Team lead | Parita Shah | 24aiml062@charusat.edu.in |
| Member | Pranay Pandey | 23it071@charusat.edu.in |
| Member | Priyanshi Dalwadi | 24dcs011@charusat.edu.in |
| Member | Jiya Shah | 24dcs116@charusat.edu.in |

---

## Problem Statement

Clinical trial operations teams can see yesterday's deviations but struggle to identify which site is becoming tomorrow's problem. Fragmented protocol rules, deviation records, and monitoring history make it difficult to prove why risk is rising or to choose an intervention with confidence.

---

## Solution

TrialGuard AI monitors 42 synthetic sites, compares visit and medication data against protocol rules using a deterministic deviation engine, classifies each finding by severity, and calculates a multi-factor site risk score. The IBM Bob integration boundary exposes 13 MCP-ready tools so an AI agent can answer evidence-backed questions about the trial — scoped by user role.

**Workflow:**

```
Protocol rules
     ↓
Patient / visit / medication data  
     ↓
Deterministic protocol comparison (deviation engine)
     ↓
Severity classification (6-factor scoring)
     ↓
Site-level risk score (multi-factor, leading indicators)
     ↓
Predictive / trend analysis
     ↓
IBM Bob investigation (MCP-ready tool boundary)
     ↓
Recommended actions
     ↓
CAPA generation
     ↓
   Audit

```

---

## Key Features

| Feature | Description |
|---|---|
| **Deviation Detection** | Rule-based engine evaluates all 8 protocol rules (R-001–R-008); detects 7 deviation types |
| **Severity Classification** | Transparent 6-factor prototype scoring (safety, data integrity, criticality, rights, magnitude, recurrence) |
| **Site Risk Engine** | Multi-factor score (0–100) with leading indicators, trend, and 6-period sparkline; deterministic with natural variation |
| **Predictive Risk** | Projected score for next monitoring period with worsening/improving/stable trend |
| **Clinical Command Center Dashboard** | TrialGuard Risk Indicator · "What Needs Your Attention" panel · Early Warning Center · Site Risk Heatmap |
| **IBM Bob Integration** | 13 MCP-ready tool contracts exposed as real MCP server (`src/mcp_server.py`); IBM Bob configured via `.bob/mcp.json`; RBAC enforced; STDIO transport |
| **TrialGuard Demo Assistant** | Local web demo adapter (NOT IBM Bob) that calls the same 13 tool contracts; clearly labelled |
| **Bob Investigation Mode** | Step-by-step site investigation showing Retrieve → Analyze → Trend → Recommend → CAPA |
| **CAPA Workflow** | Evidence-backed CAPA with visual workflow tracker; Approve/Reject (role-gated); AI root-cause clearly labelled |
| **Protocol Patient Compare** | Compare any patient against protocol eligibility rules directly from the Protocol Analysis page |
| **Global Search** | Search across sites, patients, deviations, CAPAs, and protocol rules with RBAC filtering |
| **Notification Center** | Real-time notifications from application data (worsening risk, CAPA due, major deviations) |
| **Audit Trail** | All actions logged with filterable view (action, user, free text); Bob/MCP activity visible |
| **Reports** | Trial summary, site risk, deviations, CAPA — all printable HTML with recent reports tracker |
| **RBAC** | 4 roles; server-side enforcement; site coordinator restricted to assigned site; SITE_COORDINATOR cannot access cross-site data |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, Vanilla JavaScript (SPA) |
| Backend | Python 3.10+, `http.server` (stdlib only) |
| Database | MongoDB via PyMongo (auto-falls back to in-memory) |
| IBM Bob (MCP) | `mcp[cli]>=2.2` Python SDK; 13 tools via STDIO; configured in `.bob/mcp.json` |
| AI boundary | 13 MCP-ready tool contracts (`bob_boundary.py`); shared by web demo and IBM Bob |
| Data | Deterministic synthetic data (seed=37037, no real patient data) |

---

## Quick Start

```bash
# Clone
git clone https://github.com/Anmol2k4/bob-ai-hackathon-bob-the-builder.git
cd bob-ai-hackathon-bob-the-builder

# Install dependencies (includes MCP SDK for IBM Bob integration)
pip install -r src/requirements.txt

# Run server (auto-seeds data on first start)
python src/server.py
```

Open **http://127.0.0.1:8000** in your browser.

> No external API key is required. The app uses a local Demo Bob Adapter and in-memory data if MongoDB is unavailable.

### IBM Bob Integration

Open this project folder in IBM Bob. The `.bob/mcp.json` configuration auto-registers the `trialguard` MCP server with 13 tools. IBM Bob will discover and use them to answer natural-language questions about the trial.

### With MongoDB

```bash
# Copy and edit environment variables
copy src\.env.example src\.env

# Seed the database explicitly
python src/seed.py

# Start server
python src/server.py
```

---

## Demo Accounts

| Email | Password | Role | Scope |
|---|---|---|---|
| manager@trialguard.demo | TrialGuard2026! | STUDY_MANAGER | All sites |
| site037@trialguard.demo | TrialGuard2026! | SITE_COORDINATOR | S037 only |
| auditor@trialguard.demo | TrialGuard2026! | AUDITOR | Read-only |
| admin@trialguard.demo | TrialGuard2026! | SYSTEM_ADMIN | Full access |

---

## Demo Flow (3–5 minutes)

**DETECT → PREDICT → EXPLAIN → ACT → AUDIT**

1. Log in as **manager@trialguard.demo** (STUDY_MANAGER)
2. **Dashboard** — see TrialGuard Risk Indicator, "What Needs Your Attention" (S037 highlighted), Early Warning Center, Site Risk Heatmap (42 coloured cells)
3. Dashboard heatmap: click **S037** (red) → Site detail opens
4. **Site S037**: Risk Score **87/100** · Level **HIGH** · Trend **WORSENING** · Predicted **99/100**
5. Leading indicators visible: Repeated dosing deviations · Increasing missed visits · Data-entry delays
6. Click **🔍 Investigate with Bob** → step-by-step investigation panel runs 6 tool calls in sequence
7. Expand **Investigation Evidence** on any Bob response to see tool used and data source
8. Open a `INCORRECT_DOSE` deviation: Expected **100 mg** → Actual **150 mg** · MAJOR severity
9. Evidence panel: Rule R-003 · Protocol TG-101 · Severity score 14/25 · recurrence flag
10. Navigate to **Protocol Analysis** → click **Compare Patient** on Rule R-003 → enter `P-037-019`
11. See NON-COMPLIANT result with MAJOR severity violation
12. Navigate to **CAPA Management** → open CAPA-0001 → see full workflow tracker
13. As Study Manager: click **✓ Approve CAPA** → status updates immediately
14. **Audit Trail**: filter by BOB_QUESTION → see all Bob queries logged; filter by GENERATE_CAPA
15. **Reports** → generate Site Risk Report for S037 → appears in Recent Reports list
16. Ask in Bob chat: *"hello"* → gets capability/unsupported response (not S037 risk data)

---

## Demo

| Artifact | Link |
|---|---|
| **Demo Video** | [Google Drive — Demo Recording](https://drive.google.com/drive/folders/1NC5sAVuRSfafQ3ymN-QQP0weuazMG0n2?usp=sharing) |
| **Live Demo** | Run locally — see [Quick Start](#quick-start) or [docs/setup-guide.md](docs/setup-guide.md) |
| **Screenshots** | [`demo/screenshots/`](demo/screenshots/) — 5 screenshots of the running app |

---

## Known Limitations

- **No live IBM Bob connectivity** — uses a local Demo Bob Adapter. Replacing it requires implementing one provider class (see [`docs/setup-guide.md`](docs/setup-guide.md)).
- **No persistent storage without MongoDB** — in-memory fallback means data resets on server restart.
- **Single trial protocol** — only TG-101 is modelled; multi-trial support is future work.
- **No real-time data ingestion** — all data is deterministic synthetic seed data (seed = 37037).
- **HTML reports only** — print-friendly HTML; PDF/DOCX export is not implemented.
- **Prototype severity and risk models** — not ICH/FDA/EMA guidance; not validated for regulatory use.
- **No production hardening** — no TLS, no durable session store, no rate limiting.

---

## What We're Most Proud Of

The end-to-end decision loop, completable in under 5 minutes:

1. Log in as Study Manager → see **S037 at 87/100 WORSENING** on the dashboard
2. Open a deviation: **100 mg expected → 150 mg actual**, severity score **14/25 MAJOR**
3. Ask IBM Bob *"Why is Site S037 high risk?"* → answer grounded in the database, not hallucinated
4. Ask *"What should we do?"* → specific corrective and preventive actions
5. *"Generate a CAPA for Site S037"* → CAPA-0001 with problem statement, root cause, and actions
6. Navigate to Audit Trail → every action logged

Every step is evidence-backed, role-scoped, and traceable to a specific protocol rule comparison — not ML inference.

---

## Repository Structure

```
src/                   Runnable application
  server.py            HTTP server — all API routes
  mcp_server.py        IBM Bob MCP server — 13 tools via STDIO (NEW)
  engines.py           Deviation engine, severity classifier, site risk engine
  bob_boundary.py      IBM Bob integration boundary — 13 MCP tool contracts
  synthetic_data.py    Deterministic data generator
  services.py          CAPA generation service
  database.py          MongoDB + in-memory repositories
  security.py          PBKDF2 password hashing
  models.py            Data schemas
  config.py            Settings from environment
  seed.py              Database seed script
  static/
    index.html         Full SPA
    styles.css         Enterprise design system
    app.js             Vanilla JS application
  requirements.txt     (includes mcp[cli]>=2.2)
  .env.example
  tests/
    test_core.py       100 application tests
    test_mcp_server.py 52 MCP integration tests (NEW)
    test_routing.py    45 intent routing & compare tests (NEW)

.bob/
  mcp.json             IBM Bob MCP server configuration (NEW)

docs/
  problem-statement.md
  solution-overview.md
  architecture.md
  setup-guide.md

demo/                  Demo artifacts
submission.yaml        Hackathon evaluator metadata
```

---

## Disclaimers

- **Synthetic data only.** No real patient data is used or stored.
- **Severity classification** is a prototype prioritization framework, not ICH/FDA/EMA guidance.
- **Risk scoring** is a prototype multi-factor scoring model, not a regulatory risk stratification tool.
- **Root-cause hypotheses and CAPA recommendations** are AI-generated suggestions requiring review by qualified clinical and regulatory professionals.
- **IBM Bob MCP integration** is implemented and configured (`src/mcp_server.py`, `.bob/mcp.json`). Actual tool invocation through IBM Bob depends on the IBM Bob client being installed and the workspace folder being open.
- This application is a prototype for hackathon demonstration. Not for clinical use.
