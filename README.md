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
| **Site Risk Engine** | Multi-factor score (0–100) with leading indicators, trend, and 6-period sparkline |
| **Predictive Risk** | Projected score for next monitoring period with worsening/improving/stable trend |
| **IBM Bob Integration** | 13 MCP-ready tool contracts; demo adapter calls same contracts; role-scoped |
| **CAPA Generation** | Evidence-backed problem statement, AI-generated root-cause hypothesis, corrective/preventive actions |
| **RBAC** | 4 roles; server-side enforcement; site coordinator restricted to assigned site |
| **Audit Trail** | All actions logged; login, site access, Bob queries, CAPA events |
| **Reports** | Trial summary, site risk, deviations, CAPA — all printable HTML |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, Vanilla JavaScript (SPA) |
| Backend | Python 3.10+, `http.server` (stdlib only) |
| Database | MongoDB via PyMongo (auto-falls back to in-memory) |
| AI boundary | IBM Bob integration boundary — 13 MCP-ready tool contracts |
| Data | Deterministic synthetic data (seed=37037, no real patient data) |

---

## Quick Start

```bash
# Clone
git clone https://github.com/Anmol2k4/bob-ai-hackathon-bob-the-builder.git
cd bob-ai-hackathon-bob-the-builder

# Install dependency (PyMongo — optional, app works without MongoDB)
pip install -r src/requirements.txt

# Run server (auto-seeds data on first start)
python src/server.py
```

Open **http://127.0.0.1:8000** in your browser.

> No external API key is required. The app uses a local Demo Bob Adapter and in-memory data if MongoDB is unavailable.

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

1. Log in as **manager@trialguard.demo**
2. Dashboard: 42 sites · 1128 patients · 975 deviations · 16 high-risk sites
3. High-Risk Sites table → click **Investigate** on **S037**
4. Site detail: Risk Score **87/100** · Level **HIGH** · Trend **WORSENING**
5. Leading indicators: Repeated dosing deviations · Increasing missed visits · Data-entry delays
6. Open a `INCORRECT_DOSE` deviation: Expected **100 mg** → Actual **150 mg**
7. Click **Ask IBM Bob** → ask: *"Why is Site S037 high risk?"*
8. Bob answers with evidence from the database (risk score, drivers, deviation counts)
9. Ask: *"Is this an isolated problem or a trend?"* → Bob confirms WORSENING trajectory
10. Ask: *"What should we do?"* → corrective and preventive actions
11. Ask: *"Generate a CAPA for Site S037"* → CAPA-0001 with problem statement, root cause, actions
12. Navigate to **Audit Trail** → all events logged
13. Navigate to **Reports** → generate Site Risk Report for S037

---

## Repository Structure

```
src/                   Runnable application
  server.py            HTTP server — all API routes
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
  requirements.txt
  .env.example

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
- **Bob integration** uses a local demo adapter, not a live IBM Bob endpoint.
- This application is a prototype for hackathon demonstration. Not for clinical use.
