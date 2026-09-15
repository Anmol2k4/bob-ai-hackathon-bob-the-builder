# Problem Statement

## Context

Clinical trials produce enormous volumes of protocol compliance data: visit records, dosage logs, medication histories, assessment results, and data-entry timestamps. Risk managers are responsible for monitoring this data across dozens of sites and thousands of patients — and for intervening before problems become audit findings.

## The Problem

**Operations teams can see yesterday's deviations. They cannot easily see which site is becoming tomorrow's problem.**

Specific pain points:

1. **Reactive monitoring** — deviations are detected late, after audits or sponsor visits, not during the monitoring period when intervention is still effective.

2. **Disconnected evidence** — protocol rules, visit records, and deviation logs are often in separate systems; making the connection between a rule violation and a patient record requires manual effort.

3. **No leading indicators** — existing tools count deviations but do not distinguish accelerating patterns, recurring deviation types, or compounding risk.

4. **Opaque risk scores** — when risk scores exist, their reasoning is rarely transparent; risk managers cannot explain to sites or sponsors why a score is high.

5. **Manual CAPA creation** — corrective and preventive action plans are drafted manually from scratch, even when the evidence clearly points to a recurring pattern.

6. **No AI investigation layer** — there is no natural-language way to interrogate the evidence: "Is this trend isolated or systemic?" "What should I do first?"

## Impact

Sites that go unmonitored until audit consume disproportionate sponsor resources, create data integrity risk, and — in the worst case — put patient safety at risk through dosing errors or missed assessments.

## Scope

This prototype addresses the problem within the constraints of a hackathon demonstration:

- All data is synthetic. No real patient data is used.
- The severity framework and risk scoring are prototype prioritization tools, not regulatory guidance.
- The IBM Bob integration boundary is a demo adapter; live IBM Bob connectivity is the intended next step.
- The application is not a medical device, regulatory submission tool, or replacement for qualified clinical professionals.
