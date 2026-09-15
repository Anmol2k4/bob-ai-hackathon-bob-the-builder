# TrialGuard AI — Source Reference

## Quick Start

```bash
# 1. Install dependencies (PyMongo only)
pip install -r src/requirements.txt

# 2. Copy and edit environment config (optional — app works without MongoDB)
cp src/.env.example src/.env

# 3. Seed deterministic demo data
python src/seed.py

# 4. Start the server
python src/server.py
```

Open http://127.0.0.1:8000 in your browser.

## Demo Accounts

| Email                       | Password          | Role             | Site Scope |
|-----------------------------|-------------------|------------------|------------|
| manager@trialguard.demo     | TrialGuard2026!   | STUDY_MANAGER    | All sites  |
| site037@trialguard.demo     | TrialGuard2026!   | SITE_COORDINATOR | S037 only  |
| auditor@trialguard.demo     | TrialGuard2026!   | AUDITOR          | Read-only  |
| admin@trialguard.demo       | TrialGuard2026!   | SYSTEM_ADMIN     | All        |

## Module Reference

### Entry Points

| File         | Purpose                                                         |
|--------------|-----------------------------------------------------------------|
| `server.py`  | Python stdlib HTTP server — all REST routes, sessions, RBAC     |
| `seed.py`    | Standalone seed script — recreates all demo data from scratch   |

### Core Modules

| File               | Purpose                                                                 |
|--------------------|-------------------------------------------------------------------------|
| `config.py`        | Environment-backed settings (MongoDB URI, host, port, session secret)   |
| `database.py`      | `MongoRepository` + `MemoryRepository` — auto-falls back if no Mongo    |
| `models.py`        | `RepositoryState`, `User`, `COLLECTIONS`, `ROLES` contracts             |
| `security.py`      | PBKDF2-SHA256 password hashing and verification                         |
| `synthetic_data.py`| Fixed-seed deterministic generator (42 sites, 1128 patients, ~975 devs, 7 deviation types) |
| `engines.py`       | Deviation detection engine, severity classifier, site risk engine       |
| `services.py`      | CAPA record generator with type-specific corrective/preventive actions  |
| `bob_boundary.py`  | 13 MCP-ready tool contracts, `build_bob_tools()`, `LocalDemoBobProvider`|

### Frontend

| File                 | Purpose                                               |
|----------------------|-------------------------------------------------------|
| `static/index.html`  | Single-page enterprise SPA — all 10 views, 3 modals  |
| `static/styles.css`  | Enterprise design system, risk colours, badges        |
| `static/app.js`      | Vanilla JS — auth, nav, all page renderers, Bob chat  |

### Tests

```bash
# Run all 100 tests
python -m unittest src/tests/test_core.py -v
```

| Test Class                  | What it covers                                      |
|-----------------------------|-----------------------------------------------------|
| `TestPasswordAuth`          | Hash/verify correctness and non-reversibility       |
| `TestDemoUsers`             | All 4 demo accounts seeded with correct roles       |
| `TestRBAC`                  | `_site_scope` and `_authorize` helper logic         |
| `TestCrossSiteAccess`       | Site Coordinator cannot reach another site via Bob  |
| `TestDeviationEngine`       | All 7 protocol rules + edge cases                   |
| `TestSeverityClassification`| ADMINISTRATIVE / MINOR / MAJOR tiers + disclaimers  |
| `TestSiteRisk`              | S037 = 87/100 HIGH WORSENING, 7+ high-risk sites    |
| `TestCapaGeneration`        | Required fields, AI label, priority, uniqueness     |
| `TestBobToolAuth`           | 13 tools registered, role-gated tools enforced      |
| `TestDataIntegrity`         | 42 sites, 1128+ patients, TG-101, determinism       |

## Environment Variables

| Variable            | Default                    | Description                          |
|---------------------|----------------------------|--------------------------------------|
| `MONGODB_URI`       | `mongodb://localhost:27017` | MongoDB connection string            |
| `MONGODB_DATABASE`  | `trialguard`                | Database name                        |
| `SESSION_SECRET`    | `change-me-in-production`   | Session token signing secret         |
| `APP_HOST`          | `127.0.0.1`                 | Bind address                         |
| `APP_PORT`          | `8000`                      | HTTP port                            |

Copy `.env.example` to `.env` and update values. **Do not commit `.env`.**

## Data Notes

- All patient data is **100% synthetic** — no real individuals.
- Deviation severity and site risk scores are **prototype prioritization aids only**.
- These outputs are **not based on official ICH E6, FDA, or EMA guidance**.
- Qualified clinical and regulatory review is required before any real-world use.

## IBM Bob Integration

The application ships with a `LocalDemoBobProvider` — a deterministic local adapter that
calls the same 13 MCP-ready tool contracts as the real IBM Bob integration would.

**It is clearly labelled as NOT IBM Bob.** When the IBM Bob MCP endpoint is available,
replace `LocalDemoBobProvider` with an `IBMBobProvider` that POSTs to the MCP endpoint
while keeping the same tool contracts, session-scoped `build_bob_tools()` call, and
role-based permission checks intact.

See [`bob_boundary.py`](bob_boundary.py) and [`docs/architecture.md`](../docs/architecture.md)
for full MCP tool contract specifications.
