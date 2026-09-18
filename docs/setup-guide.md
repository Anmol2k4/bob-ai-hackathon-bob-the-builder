# Setup Guide — TrialGuard AI

## Requirements

- Python 3.10 or later
- pip
- MongoDB 6+ (optional — app runs in-memory without it)
- A modern browser (Chrome, Firefox, Edge)
- IBM Bob (for real MCP integration)

## Installation

```bash
git clone https://github.com/Anmol2k4/bob-ai-hackathon-bob-the-builder.git
cd bob-ai-hackathon-bob-the-builder
pip install -r src/requirements.txt
```

This installs:
- `pymongo` — MongoDB driver
- `python-dotenv` — environment file loading
- `mcp[cli]>=2.2` — Model Context Protocol Python SDK (required for IBM Bob integration)

## Running (in-memory, no MongoDB needed)

```bash
python src/server.py
```

Open **http://127.0.0.1:8000**

The server auto-seeds all demo data on startup when no data is found. No configuration is needed.

## Running with MongoDB

1. Copy the environment template:
   ```bash
   copy src\.env.example src\.env    # Windows
   cp src/.env.example src/.env      # Mac/Linux
   ```

2. Edit `src/.env`:
   ```
   MONGODB_URI=mongodb://127.0.0.1:27017
   MONGODB_DATABASE=trialguard
   SESSION_SECRET=change-this-to-a-random-secret
   ```

3. Seed the database:
   ```bash
   python src/seed.py
   ```

4. Start the server:
   ```bash
   python src/server.py
   ```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URI` | `mongodb://127.0.0.1:27017` | MongoDB connection string |
| `MONGODB_DATABASE` | `trialguard` | Database name |
| `SESSION_SECRET` | `local-demo-session-secret` | Session signing secret (change in production) |
| `APP_HOST` | `127.0.0.1` | Server bind address |
| `APP_PORT` | `8000` | Server port |
| `SESSION_HOURS` | `8` | Session lifetime in hours |

## Demo Accounts

| Email | Password | Role |
|---|---|---|
| manager@trialguard.demo | TrialGuard2026! | STUDY_MANAGER |
| site037@trialguard.demo | TrialGuard2026! | SITE_COORDINATOR (S037 only) |
| auditor@trialguard.demo | TrialGuard2026! | AUDITOR (read-only) |
| admin@trialguard.demo | TrialGuard2026! | SYSTEM_ADMIN |

## Seeding

The seed script (`src/seed.py`) generates:

- 42 synthetic clinical sites
- 1128 synthetic patients
- ~5100 synthetic visits
- ~1250 synthetic medication records
- ~975 protocol deviations (detected by the rule-based engine across all 8 rules, 7 deviation types)
- 42 site risk scores
- 3 pre-seeded CAPA records
- 4 demo users
- 17 seed audit events

All data is deterministic — the same dataset is produced every time (seed = 37037).

Re-run `python src/seed.py` at any time to restore the original demo state.

## Starting the Server

```bash
python src/server.py
```

Output:
```
============================================================
  TrialGuard AI — Clinical Trial Risk Monitor
============================================================
  URL:      http://127.0.0.1:8000
  Backend:  memory        (or: mongodb)
  Data:     42 sites · 1128 patients
  ...
============================================================
```

## IBM Bob Integration

TrialGuard now exposes a **real MCP server** for IBM Bob integration, in addition to the existing local demo adapter.

### Option A — Web Demo (existing, always works)

The app ships with a local Demo Bob Adapter. It calls the same 13 MCP-ready tool contracts that a real IBM Bob MCP endpoint uses.

### Option B — Real IBM Bob MCP Integration (IMPLEMENTED)

IBM Bob connects to TrialGuard through the MCP protocol using STDIO transport.

#### Configuration

The `.bob/mcp.json` file at the project root is already configured. Open this project folder in IBM Bob and the `trialguard` MCP server will appear in the MCP panel.

#### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TRIALGUARD_BOB_ROLE` | `STUDY_MANAGER` | Bob's RBAC role |
| `TRIALGUARD_BOB_USER_ID` | `bob-demo` | Bob's user identity |
| `TRIALGUARD_BOB_SITE_ID` | `` (empty) | Site restriction (empty = all sites) |

#### Start the MCP server manually

```bash
python src/mcp_server.py
```

The server communicates via STDIO (stdout = MCP protocol, stderr = diagnostics). Do not add other processes reading stdout when running the MCP server.

#### Test MCP server with MCP CLI

```bash
# List available tools
mcp run src/mcp_server.py

# Interactive inspector (requires browser)
mcp dev src/mcp_server.py
```

#### Available MCP Tools

All 13 TrialGuard tools are exposed:

| Tool | Description |
|---|---|
| `get_trial_overview` | Trial-level KPIs (sites, patients, deviations, CAPAs) |
| `list_high_risk_sites` | Ranked list of high-risk sites with scores |
| `get_site_risk` | Current + projected risk for one site |
| `explain_site_risk` | Evidence-backed risk driver explanation |
| `list_site_deviations` | Protocol deviations for a site (filterable by severity) |
| `get_deviation` | Full record for a single deviation |
| `search_protocol_rules` | Search TG-101 protocol rules by keyword |
| `compare_patient_to_protocol` | Patient eligibility compliance check |
| `get_site_trends` | Risk trend, sparkline, deviation type breakdown |
| `recommend_site_actions` | Corrective and preventive action recommendations |
| `generate_capa` | CAPA draft from real deviation records |
| `get_capa_status` | CAPA records and status summary |
| `generate_risk_report` | Structured risk report for a site |

#### RBAC Behavior

The MCP server enforces the same RBAC as the web application:

| Role | Access |
|---|---|
| `STUDY_MANAGER` | All tools, all sites |
| `SITE_COORDINATOR` | Site tools for assigned site only; no CAPA/recommendations |
| `AUDITOR` | Read-only tools; no CAPA/recommendations |
| `SYSTEM_ADMIN` | All tools, all sites |

#### Example IBM Bob Prompts

After connecting IBM Bob to the `trialguard` MCP server, try:

```
Give me an overview of the TrialGuard clinical trial.
Which sites currently have the highest risk?
Why is Site S037 high risk?
Is the risk at Site S037 isolated or does it show a worsening trend?
What are the main deviations contributing to Site S037's risk?
What corrective and preventive actions would you recommend for Site S037?
Generate a CAPA draft for Site S037 using the evidence available in TrialGuard.
Prepare a risk report for the current high-risk sites.
```

In the web Demo Bob Adapter (web chatbot), site comparison is also supported:

```
Compare S037 and S008
Compare S001 vs S032
Generate a comparison report of S001 and S037
```

## Troubleshooting

**"MongoDB unavailable; using in-memory repository"**
This is expected if MongoDB is not running. The app works fully in-memory.

**Port 8000 already in use**
Set `APP_PORT=8001` in `.env` or pass the port as an environment variable.

**Login fails**
Make sure the seed has run and the correct password `TrialGuard2026!` is used.

**MCP server not appearing in IBM Bob**
1. Confirm the workspace folder is open in IBM Bob (MCP servers do not connect in an empty window).
2. Check that `.bob/mcp.json` exists at the project root.
3. Open the MCP panel in IBM Bob to see the connection status and any error messages.
4. Run `python src/mcp_server.py` in a terminal — the server should start silently (diagnostics go to stderr only).
5. Confirm `python` is on your PATH and `mcp[cli]>=2.2` is installed (`pip install "mcp[cli]"`).

**MCP server prints output to stdout**
stdout is reserved for MCP protocol. Do not add `print()` statements to `mcp_server.py`. All diagnostics use `logging` (stderr).

**MCP permission error for a tool**
The identity (role/user/site) is configured in `.bob/mcp.json` env vars. Change `TRIALGUARD_BOB_ROLE` to `SYSTEM_ADMIN` for full access during testing.

**Running tests**
```bash
# All tests (197 total)
cd src && python -m pytest tests/ -v

# Existing application tests (100 tests)
cd src && python tests/test_core.py

# MCP server tests (52 tests: tool discovery, invocations, RBAC, error handling)
cd src && python tests/test_mcp_server.py

# Intent routing & compare tests (45 tests)
cd src && python tests/test_routing.py
```
