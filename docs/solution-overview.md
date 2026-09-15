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

## What Is Out of Scope (Prototype Limitations)

- Live IBM Bob connectivity (demo adapter used)
- Real-time data ingestion (synthetic seed data only)
- PDF/DOCX report export (HTML print-friendly reports)
- Multi-trial support (single TG-101 protocol)
- Regulatory submission workflow
- Real patient data (strictly prohibited)
