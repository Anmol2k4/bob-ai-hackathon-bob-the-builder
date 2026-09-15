# Setup Guide

## Prerequisites

- Python 3.10 or newer
- A modern browser
- No external database or API key for the local seeded demo

## Installation

```bash
git clone https://github.com/Anmol2k4/bob-ai-hackathon-bob-the-builder.git
cd bob-ai-hackathon-bob-the-builder
```

The prototype uses only the Python standard library, so there is no dependency install step. Optional IBM Bob configuration can be copied from `src/.env.example`; it is not required for the local demo.

## Running the Application

```bash
python src/app.py
```

Open `http://127.0.0.1:8000`.

## Quick Demo

1. Start on Trial Risk Radar and point out S037 as the fastest-deteriorating site.
2. Read the Site Intelligence panel: risk 87, +13 velocity, and 72% concentration in V3 scheduling.
3. Show the evidence IDs and the confidence signal for five complete monitoring periods.
4. Read Bob's answer to “Why is S037 becoming risky?” and identify its three sources.
5. In Scenario Lab, leave the reduction at 30% and choose **Run scenario**. The projected risk is 77 and the status changes to watch.

## Validation

```bash
python -m py_compile src/app.py
```

## Troubleshooting

| Issue | Solution |
|---|---|
| Port 8000 is already in use | Stop the other process or change the port tuple in `src/app.py`. |
| Browser shows an unavailable service message | Confirm `python src/app.py` is still running and reload the page. |
| IBM Bob credentials are unavailable | The local seeded investigation works without credentials. |
