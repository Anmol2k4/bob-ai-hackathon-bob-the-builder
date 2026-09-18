"""
TrialGuard AI — CAPA and utility services
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from collections import Counter


def generate_capa_record(site_id: str, deviations: list[dict], created_by: str) -> dict:
    """Generate a CAPA record from selected deviations."""
    if not deviations:
        deviation_ids = []
        problem_statement = f"Potential protocol compliance issues at Site {site_id}."
        dominant_type = "UNKNOWN"
    else:
        deviation_ids = [d["deviation_id"] for d in deviations]
        type_counts = Counter(d["type"] for d in deviations)
        dominant_type = type_counts.most_common(1)[0][0]
        major_count = sum(1 for d in deviations if d["severity"] == "MAJOR")
        problem_statement = (
            f"Site {site_id} has {len(deviations)} protocol deviation(s) requiring corrective action, "
            f"including {major_count} major deviation(s). "
            f"The most frequent deviation type is {dominant_type.replace('_', ' ').title()}."
        )

    corrective_actions = _corrective_actions(dominant_type)
    preventive_actions = _preventive_actions(dominant_type)
    priority = "HIGH" if any(d.get("severity") == "MAJOR" for d in deviations) else "MEDIUM"

    return {
        "capa_id": f"CAPA-{uuid.uuid4().hex[:6].upper()}",
        "site_id": site_id,
        "deviation_ids": deviation_ids,
        "problem_statement": problem_statement,
        "root_cause": (
            f"AI-generated hypothesis (requires qualified review): "
            f"Insufficient secondary verification for {dominant_type.replace('_', ' ').lower()} "
            f"procedures at Site {site_id}. Contributing factors may include staff training gaps, "
            f"workload pressure, or unclear protocol communication."
        ),
        "corrective_actions": corrective_actions,
        "preventive_actions": preventive_actions,
        "priority": priority,
        "owner": "Site Investigator",
        "status": "OPEN",
        "due_date": _due_date(priority),
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": (
            "Root cause hypotheses and recommended actions are AI-generated suggestions. "
            "Review by qualified clinical and regulatory professionals is required before implementation."
        ),
    }


def _due_date(priority: str) -> str:
    from datetime import timedelta
    days = {"HIGH": 14, "MEDIUM": 30, "LOW": 60}.get(priority, 30)
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def _corrective_actions(deviation_type: str) -> list[str]:
    base = [
        "Review all affected patient records for completeness and accuracy",
        "Notify site investigator and study sponsor of identified deviations",
        "Document findings in the Trial Master File",
    ]
    specific = {
        "INCORRECT_DOSE": [
            "Verify current dose for all affected patients with treating physician",
            "Assess safety impact in collaboration with medical monitor",
            "Conduct immediate dose reconciliation for affected records",
        ],
        "MISSED_VISIT": [
            "Contact patients who missed scheduled visits to reschedule promptly",
            "Assess clinical impact of missed assessments with medical monitor",
            "Perform retrospective data entry for all missed visit windows",
        ],
        "PROHIBITED_MEDICATION": [
            "Review concomitant medication records for all site patients",
            "Consult medical monitor for protocol deviation waivers as applicable",
            "Document risk assessment for all identified prohibited medications",
        ],
        "MISSING_ASSESSMENT": [
            "Identify and complete all outstanding required assessments where clinically feasible",
            "Assess impact on primary and secondary endpoint data integrity",
            "Document any assessments that cannot be retrospectively completed",
        ],
        "ELIGIBILITY_VIOLATION": [
            "Conduct full eligibility re-review for all enrolled patients",
            "Consult regulatory team regarding any required protocol amendments",
            "Assess impact on primary analysis dataset with biostatistics team",
        ],
        "LATE_DATA_ENTRY": [
            "Complete all outstanding data entry within 48 hours",
            "Review data entry logs to identify systemic patterns",
            "Verify data accuracy for all late-entered records",
        ],
        "VISIT_OUTSIDE_WINDOW": [
            "Review all affected visit records for assessment completeness",
            "Assess impact on study endpoints with the medical monitor",
            "Document visit window deviations with clinical justification",
        ],
    }.get(deviation_type, [])
    return specific + base


def _preventive_actions(deviation_type: str) -> list[str]:
    base = [
        "Increase on-site monitoring frequency for the next two monitoring periods",
        "Conduct a site performance review meeting with the investigator team",
        "Implement site-specific risk mitigation plan",
    ]
    specific = {
        "INCORRECT_DOSE": [
            "Implement mandatory dual-pharmacist verification for all dose preparations",
            "Add electronic dose-confirmation checklist to site workflow",
            "Schedule targeted dosing protocol training for all site staff",
        ],
        "MISSED_VISIT": [
            "Implement patient appointment reminder system (phone/SMS)",
            "Add visit-window alerts to site's clinical management system",
            "Assign dedicated patient liaison for scheduling at this site",
        ],
        "PROHIBITED_MEDICATION": [
            "Update site pharmacy with current prohibited medication list",
            "Add concomitant medication screen to visit start checklist",
            "Schedule pharmacist consultation training for all site prescribers",
        ],
        "MISSING_ASSESSMENT": [
            "Add assessment completion checklist to visit workflow",
            "Implement real-time visit completion tracking dashboard",
            "Create assessment reminder prompts in electronic data capture system",
        ],
        "ELIGIBILITY_VIOLATION": [
            "Implement mandatory re-screening before enrollment for all criteria",
            "Add eligibility checklist sign-off to enrollment authorization",
            "Schedule eligibility criteria refresher training for site staff",
        ],
        "LATE_DATA_ENTRY": [
            "Implement 24-hour data entry SLA with automated reminders",
            "Add data entry dashboard for site coordinator daily review",
            "Schedule data management training focused on entry timeliness",
        ],
        "VISIT_OUTSIDE_WINDOW": [
            "Add visit-window calendar alerts to site scheduling system",
            "Implement early-warning notification 3 days before window closure",
            "Create visit scheduling protocol card for all site staff",
        ],
    }.get(deviation_type, [])
    return specific + base


def analyze_deviation_pattern(
    site_id: str,
    deviations: list[dict],
    patients: list[dict] | None = None,
) -> dict:
    """
    Analyze deviation patterns at a site: identify recurring types, affected patients,
    and cross-patient spread.

    Returns a structured pattern analysis suitable for investigation workspace and Bob responses.
    """
    site_devs = [d for d in deviations if d.get("site_id") == site_id]
    if not site_devs:
        return {
            "site_id": site_id,
            "patterns": [],
            "recurring_types": [],
            "isolated_types": [],
            "most_concerning": None,
        }

    from collections import defaultdict
    # Group by type
    by_type: dict[str, list[dict]] = defaultdict(list)
    for dev in site_devs:
        dtype = dev.get("type", "UNKNOWN")
        by_type[dtype].append(dev)

    patterns = []
    for dtype, devs in by_type.items():
        affected_patients = list({d.get("patient_id") for d in devs if d.get("patient_id")})
        unique_patient_count = len(affected_patients)
        dates = sorted(
            [d.get("detected_at") or d.get("created_at", "")
             for d in devs if d.get("detected_at") or d.get("created_at")]
        )
        is_recurring = len(devs) > 2
        cross_patient = unique_patient_count > 1
        if is_recurring and cross_patient:
            assessment = "RECURRING across multiple patients"
        elif is_recurring:
            assessment = "RECURRING — same patient"
        elif cross_patient:
            assessment = "ISOLATED across multiple patients"
        else:
            assessment = "ISOLATED"

        patterns.append({
            "deviation_type": dtype,
            "occurrences": len(devs),
            "affected_patients": affected_patients[:10],
            "unique_patient_count": unique_patient_count,
            "first_occurrence": dates[0] if dates else None,
            "latest_occurrence": dates[-1] if dates else None,
            "is_recurring": is_recurring,
            "cross_patient": cross_patient,
            "assessment": assessment,
        })

    # Sort by occurrences desc
    patterns.sort(key=lambda p: (-p["occurrences"], p["deviation_type"]))

    recurring_types = [p["deviation_type"] for p in patterns if p["is_recurring"]]
    isolated_types = [p["deviation_type"] for p in patterns if not p["is_recurring"]]

    # Most concerning = highest occurrences with MAJOR severity preference
    major_types = {d.get("type") for d in site_devs if d.get("severity") == "MAJOR"}
    concerning_patterns = [p for p in patterns if p["deviation_type"] in major_types]
    most_concerning = (
        concerning_patterns[0]["deviation_type"] if concerning_patterns
        else (patterns[0]["deviation_type"] if patterns else None)
    )

    return {
        "site_id": site_id,
        "patterns": patterns,
        "recurring_types": recurring_types,
        "isolated_types": isolated_types,
        "most_concerning": most_concerning,
    }
