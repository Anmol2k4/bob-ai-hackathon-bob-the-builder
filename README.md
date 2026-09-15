# Clinical Trial Risk Intelligence Copilot

> **Bob the Builder · AI track**

Clinical Trial Risk Intelligence Copilot helps clinical trial operations teams identify which site is becoming tomorrow's problem, prove why with an evidence chain, and test what to do next.

## Team

| Role | Name | Contact |
|---|---|---|
| Team lead | Parita Shah | 24aiml062@charusat.edu.in |
| Member | Pranay Pandey | 23it071@charusat.edu.in |
| Member | Priyanshi Dalwadi | 24dcs011@charusat.edu.in |
| Member | Jiya Shah | 24dcs116@charusat.edu.in |

## Problem Statement

Clinical trial operations teams can see yesterday's deviations, but struggle to identify which site is becoming tomorrow's problem. Protocol rules, deviation records, and monitoring history are often disconnected, making it difficult to prove why risk is rising and choose an intervention with confidence.

## Solution

The Copilot turns verified protocol rules and synthetic site data into an evidence-backed risk radar. It combines transparent trajectory analysis, linked evidence, an IBM Bob investigation boundary, and intervention simulation so an operations lead can move from finding risk to testing an action in one workflow.

## Key Features

- **Emerging-risk radar:** Prioritizes site deterioration using transparent trend and velocity signals.
- **Evidence chain:** Links a site's risk drivers to verified rules, monitoring periods, patients, and deviation IDs.
- **Bob investigation:** Provides a natural-language investigation surface backed by risk, evidence, and rule sources.
- **Scenario lab:** Projects the effect of reducing the dominant operational driver before action is taken.
- **Confidence signals:** Shows history completeness and evidence volume alongside recommendations.

## Tech Stack

Python standard-library HTTP server, JavaScript, HTML, CSS, IBM Bob integration boundary, MCP-ready tool contract, and deterministic synthetic clinical-trial data. The architecture is designed to add SQLite persistence and live IBM services without changing the product workflow.

## Run Locally

```bash
git clone https://github.com/Anmol2k4/bob-ai-hackathon-bob-the-builder.git
cd bob-ai-hackathon-bob-the-builder
python src/app.py
```

Open `http://127.0.0.1:8000`. No external API key is needed for the seeded local demo. See [docs/setup-guide.md](docs/setup-guide.md) for the full setup and demo flow.

## Repository Structure

```text
src/                  Runnable local prototype and static dashboard
docs/                 Problem, solution, architecture, and setup documentation
demo/                 Demo links and screenshot requirements
presentation/         Slide-deck location and recommended story
submission.yaml       Structured evaluator metadata
```

## Demo

| Artifact | Status |
|---|---|
| Demo video | [demo/demo-video-link.txt](demo/demo-video-link.txt) · Not ready |
| Live demo | [demo/live-demo-url.txt](demo/live-demo-url.txt) · Not deployed |
| Screenshots | [demo/screenshots/](demo/screenshots/) · Capture after running locally |
| Presentation | [presentation/](presentation/) · Deck not ready |

## Known Limitations

- The current slice uses seeded synthetic data; no real patient or trial data is included.
- IBM Bob is represented by a local adapter response until endpoint credentials and deployment details are available.
- Live protocol PDF extraction, persistent SQLite storage, CAPA persistence, and authentication are planned next.

## What We're Most Proud Of

The strongest part of the submission is the decision loop: S037 is surfaced because its risk is accelerating, its dominant driver is proven through linked evidence, Bob explains the finding, and the scenario lab shows how a targeted intervention changes projected risk.
