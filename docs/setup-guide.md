# Setup Guide — TrialGuard AI

## Requirements

- Python 3.10 or later
- pip
- MongoDB 6+ (optional — app runs in-memory without it)
- A modern browser (Chrome, Firefox, Edge)

## Installation

```bash
git clone https://github.com/Anmol2k4/bob-ai-hackathon-bob-the-builder.git
cd bob-ai-hackathon-bob-the-builder
pip install -r src/requirements.txt
```

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

The app ships with a local Demo Bob Adapter. It calls the same 13 MCP-ready tool contracts that a real IBM Bob MCP endpoint would use.

To connect a real IBM Bob endpoint:

1. Implement `IBMBobProvider` with the same `.answer(question, user, tools)` interface
2. Replace `LocalDemoBobProvider` in `server.py` with your provider
3. No other changes to the application are needed

## Troubleshooting

**"MongoDB unavailable; using in-memory repository"**
This is expected if MongoDB is not running. The app works fully in-memory.

**Port 8000 already in use**
Set `APP_PORT=8001` in `.env` or pass the port as an environment variable.

**Login fails**
Make sure the seed has run and the correct password `TrialGuard2026!` is used.
