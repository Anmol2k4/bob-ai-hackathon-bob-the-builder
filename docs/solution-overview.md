# Solution Overview — TrialGuard AI

## One-line Summary

TrialGuard AI combines deterministic protocol deviation detection, transparent site risk scoring, predictive trend analysis, and an IBM Bob investigation boundary into one clinical-trial monitoring workflow.

## The Decision Loop

```
FIND   → Which site should I look at next?
PROVE  → Why is it risky? What's the evidence?
PREDICT→ Is this getting worse or better?
TEST   → What happens if I take action?
ACT    → Generate CAPA, assign owner, set due date.
```

Each step is handled by a different component of the application, and all steps are reachable from the Ask IBM Bob panel in a single conversation.

## Key Differentiators

### 1. Deterministic Deviation Detection

A rule-based engine compares every synthetic visit and medication record against 8 protocol rules. Each deviation includes:

- What was expected (the protocol rule)
- What actually happened (the patient record)
- Which rule was violated and why
- Severity score with a factor-by-factor breakdown

This is not ML inference. Every finding is traceable to a specific comparison.

### 2. Transparent Severity Classification

Severity is calculated from 6 configurable factors (safety impact, data integrity, protocol criticality, participant rights, magnitude, recurrence). The score and each contributing factor are shown to the user. The disclaimer that these are prototype thresholds — not ICH/FDA guidance — is always displayed.

### 3. Predictive Site Risk

Site risk is a multi-factor score (0–100) that goes beyond counting deviations:

- Weighted heavily by major deviation count
- Penalises recurring deviation types (same problem repeating = systemic risk)
- Detects recent acceleration (more major findings in recent periods vs earlier)
- Generates a 6-period sparkline showing the trajectory

The predicted score for the next monitoring period is displayed with clear language: "projected", "estimated", "risk indicator".

### 4. IBM Bob Integration Boundary

The Bob boundary is the primary differentiator for the AI track:

- 13 MCP-ready tool contracts with input/output schemas
- Every Bob answer is grounded in a tool result — no hallucination
- User permissions are inherited by Bob (site coordinator cannot ask Bob about other sites)
- The Demo Adapter is clearly labelled as not IBM Bob
- Replacing it with a real IBM Bob MCP endpoint requires one code change

### 5. CAPA Generation

CAPA records are generated from actual deviations. The system:

- Identifies the dominant deviation type for the site
- Generates a specific problem statement from the evidence
- Provides deviation-type-specific corrective and preventive actions (7 sets)
- Labels root-cause hypotheses as AI-generated suggestions requiring qualified review
- Records the CAPA creation in the audit trail

## What the User Experience Looks Like

A Study Manager opens the app and immediately sees the dashboard: **42 sites, 1128 patients, 975 deviations, 16 high-risk sites**. No configuration, no query language — the risk picture is immediate.

**Typical investigation flow (3–5 minutes):**

1. **Dashboard** — The high-risk sites table is sorted by risk score. S037 is at the top: **87/100, WORSENING**. One click opens the site detail.

2. **Site detail** — The manager sees the multi-factor score breakdown, a 6-period sparkline showing acceleration, and the leading indicators: repeated dosing deviations, increasing missed visits, data-entry delays. The predicted score for the next period is shown with explicit "projected" language.

3. **Deviation drill-down** — Clicking a `INCORRECT_DOSE` finding shows the exact comparison: **100 mg expected → 150 mg actual**, the rule violated (R-003), and the severity score **14/25 MAJOR** with factor-by-factor breakdown.

4. **Ask IBM Bob** — The manager opens the Bob panel (right-side drawer) and types a question in plain English: *"Why is Site S037 high risk?"* Bob answers in a few seconds with evidence pulled directly from the database — risk score, drivers, deviation counts — not a generic response. Follow-up questions work in the same conversation: *"Is this a trend?"*, *"What should we do?"*

5. **Generate CAPA** — One more message: *"Generate a CAPA for Site S037"*. Bob generates CAPA-0001: problem statement drawn from the dominant deviation type, a root-cause hypothesis labelled as AI-generated, and deviation-type-specific corrective and preventive actions.

6. **Audit Trail and Reports** — Every action taken — login, site access, Bob query, CAPA creation — is logged and visible. The manager can generate a printable Site Risk Report from the Reports page.

**Role-scoped access:** A Site Coordinator logging in with `site037@trialguard.demo` sees only S037. Asking Bob about any other site returns a permission error — enforced server-side, not just in the UI.

## What Is Out of Scope (Prototype Limitations)

- Live IBM Bob connectivity (demo adapter used)
- Real-time data ingestion (synthetic seed data only)
- PDF/DOCX report export (HTML print-friendly reports)
- Multi-trial support (single TG-101 protocol)
- Regulatory submission workflow
- Real patient data (strictly prohibited)
