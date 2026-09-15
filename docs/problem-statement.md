# Problem Statement

## Who Is Affected

**Primary audience:** Clinical trial operations teams — specifically Study Managers, Risk Managers, and Clinical Research Associates (CRAs) responsible for monitoring multi-site trials. Secondary audiences include Sponsors who fund trials and Auditors who assess compliance. A mid-size trial typically spans 20–60 sites and 500–2,000 patients, with one risk manager often responsible for all of them.

## The Problem

**Operations teams can see yesterday's deviations. They cannot easily see which site is becoming tomorrow's problem.**

Specific pain points:

1. **Reactive monitoring** — deviations are detected late, after audits or sponsor visits, not during the monitoring period when intervention is still effective.

2. **Disconnected evidence** — protocol rules, visit records, and deviation logs are often in separate systems; making the connection between a rule violation and a patient record requires manual effort.

3. **No leading indicators** — existing tools count deviations but do not distinguish accelerating patterns, recurring deviation types, or compounding risk.

4. **Opaque risk scores** — when risk scores exist, their reasoning is rarely transparent; risk managers cannot explain to sites or sponsors why a score is high.

5. **Manual CAPA creation** — corrective and preventive action plans are drafted manually from scratch, even when the evidence clearly points to a recurring pattern.

6. **No AI investigation layer** — there is no natural-language way to interrogate the evidence: "Is this trend isolated or systemic?" "What should I do first?"

## Why Existing Solutions Don't Solve It

Current clinical trial management systems (CTMS) and electronic data capture (EDC) platforms provide deviation logs and basic compliance dashboards. They fall short because:

- **They are record systems, not reasoning systems.** They store what happened; they do not explain why risk is rising or predict where it will rise next.
- **Risk scores, where they exist, are black boxes.** Managers cannot drill into a score to see which factors drive it, making it impossible to prioritise interventions or justify decisions to sponsors.
- **CAPA is a manual process.** Most platforms provide a form to fill in; none generate evidence-linked action plans from the deviation record automatically.
- **There is no natural-language interface.** Interrogating the evidence requires navigating multiple screens, exporting data, and constructing the argument manually — a process that can take hours per site.

## Quantified Pain

- Industry estimates put the cost of a single protocol deviation remediation at **$5,000–$50,000** depending on severity, regulatory impact, and required documentation.
- Dosing deviations (the most common finding in our prototype) are among the top causes of FDA 483 observations and warning letters, which can halt a trial.
- A risk manager monitoring 42 sites manually spends an estimated **4–6 hours per week** just aggregating deviation data before any analysis begins.
- Late-detected deviations that require retrospective CAPA add an average of **2–4 weeks** to trial timelines.

## Why This Problem Matters *Now*

Three converging forces make this the right time to solve it:

1. **Trial complexity is increasing.** Decentralised and hybrid trials add more sites, more remote visits, and more data entry points — amplifying the deviation surface.
2. **Regulatory scrutiny is tightening.** FDA and EMA risk-based monitoring guidance (ICH E6 R2/R3) explicitly requires sponsors to demonstrate proactive, evidence-based risk management — not just retrospective audit trails.
3. **AI tooling has matured.** Tools like IBM Bob now provide a structured, permission-scoped interface for grounding AI answers in real evidence — making it possible to build an investigation layer that is reliable enough to act on.

## Impact

Sites that go unmonitored until audit consume disproportionate sponsor resources, create data integrity risk, and — in the worst case — put patient safety at risk through dosing errors or missed assessments.

## Scope

This prototype addresses the problem within the constraints of a hackathon demonstration:

- All data is synthetic. No real patient data is used.
- The severity framework and risk scoring are prototype prioritization tools, not regulatory guidance.
- The IBM Bob integration boundary is a demo adapter; live IBM Bob connectivity is the intended next step.
- The application is not a medical device, regulatory submission tool, or replacement for qualified clinical professionals.
