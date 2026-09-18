"""
TrialGuard AI — IBM Bob Integration Boundary

This module defines the MCP-ready tool contract boundary between the TrialGuard
application and IBM Bob. The LocalDemoBobProvider is a deterministic local adapter
for demonstration — it is NOT IBM Bob.

When the IBM Bob MCP endpoint is available, replace LocalDemoBobProvider with
an IBMBobProvider that calls the MCP server while preserving the same tool contracts.
"""
from __future__ import annotations
from typing import Callable, Any

from models import User


# ─── tool contract registry ───────────────────────────────────────────────────

TOOL_REGISTRY = {
    "get_trial_overview": {
        "description": "Return trial-level KPIs visible to the authenticated user.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "AUDITOR", "SYSTEM_ADMIN"],
    },
    "list_high_risk_sites": {
        "description": "Return ranked list of high-risk sites with leading indicators.",
        "input_schema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 10}}, "required": []},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "AUDITOR", "SYSTEM_ADMIN"],
    },
    "get_site_risk": {
        "description": "Return current and projected risk score for one site.",
        "input_schema": {"type": "object", "properties": {"site_id": {"type": "string"}}, "required": ["site_id"]},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "SITE_COORDINATOR", "AUDITOR", "SYSTEM_ADMIN"],
    },
    "explain_site_risk": {
        "description": "Return evidence-backed risk driver explanation for one site.",
        "input_schema": {"type": "object", "properties": {"site_id": {"type": "string"}}, "required": ["site_id"]},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "SITE_COORDINATOR", "AUDITOR", "SYSTEM_ADMIN"],
    },
    "list_site_deviations": {
        "description": "List protocol deviations for a site the user is authorized to access.",
        "input_schema": {"type": "object", "properties": {"site_id": {"type": "string"}, "severity": {"type": "string"}}, "required": ["site_id"]},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "SITE_COORDINATOR", "AUDITOR", "SYSTEM_ADMIN"],
    },
    "get_deviation": {
        "description": "Return one deviation with full evidence and classification.",
        "input_schema": {"type": "object", "properties": {"deviation_id": {"type": "string"}}, "required": ["deviation_id"]},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "SITE_COORDINATOR", "AUDITOR", "SYSTEM_ADMIN"],
    },
    "search_protocol_rules": {
        "description": "Search structured protocol rules by domain or keyword.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": []},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "SITE_COORDINATOR", "AUDITOR", "SYSTEM_ADMIN"],
    },
    "compare_patient_to_protocol": {
        "description": "Compare a synthetic patient record against protocol eligibility rules.",
        "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}}, "required": ["patient_id"]},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "SITE_COORDINATOR", "SYSTEM_ADMIN"],
    },
    "get_site_trends": {
        "description": "Return deviation trend data for a site.",
        "input_schema": {"type": "object", "properties": {"site_id": {"type": "string"}}, "required": ["site_id"]},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "SITE_COORDINATOR", "AUDITOR", "SYSTEM_ADMIN"],
    },
    "recommend_site_actions": {
        "description": "Generate recommended corrective and preventive actions for a site.",
        "input_schema": {"type": "object", "properties": {"site_id": {"type": "string"}}, "required": ["site_id"]},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "SYSTEM_ADMIN"],
    },
    "generate_capa": {
        "description": "Create a CAPA suggestion based on actual site deviations.",
        "input_schema": {"type": "object", "properties": {"site_id": {"type": "string"}}, "required": ["site_id"]},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "SYSTEM_ADMIN"],
    },
    "get_capa_status": {
        "description": "Return CAPA records and their status.",
        "input_schema": {"type": "object", "properties": {"site_id": {"type": "string"}}, "required": []},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "SITE_COORDINATOR", "AUDITOR", "SYSTEM_ADMIN"],
    },
    "generate_risk_report": {
        "description": "Generate a structured risk report payload for a site.",
        "input_schema": {"type": "object", "properties": {"site_id": {"type": "string"}}, "required": ["site_id"]},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "AUDITOR", "SYSTEM_ADMIN"],
    },
    "get_site_risk_history": {
        "description": "Return stored monthly risk score snapshots (6 periods) for a site.",
        "input_schema": {"type": "object", "properties": {"site_id": {"type": "string"}}, "required": ["site_id"]},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "SITE_COORDINATOR", "AUDITOR", "SYSTEM_ADMIN"],
    },
    "analyze_deviation_pattern": {
        "description": "Analyze recurring deviation patterns at a site: recurrence, affected patients, cross-patient spread.",
        "input_schema": {"type": "object", "properties": {"site_id": {"type": "string"}}, "required": ["site_id"]},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "SITE_COORDINATOR", "AUDITOR", "SYSTEM_ADMIN"],
    },
    "get_affected_patients": {
        "description": "Return patients affected by a specific deviation type at a site.",
        "input_schema": {"type": "object", "properties": {"site_id": {"type": "string"}, "deviation_type": {"type": "string"}}, "required": ["site_id", "deviation_type"]},
        "output_schema": {"type": "object"},
        "roles": ["STUDY_MANAGER", "SITE_COORDINATOR", "AUDITOR", "SYSTEM_ADMIN"],
    },
}


def tool_contracts() -> list[dict]:
    return [
        {
            "tool_name": name,
            "description": meta["description"],
            "input_schema": meta["input_schema"],
            "output_schema": meta["output_schema"],
            "authorization_requirements": {
                "authenticated": True,
                "allowed_roles": meta["roles"],
                "site_scope_enforced": True,
            },
        }
        for name, meta in TOOL_REGISTRY.items()
    ]


# ─── tool implementations ─────────────────────────────────────────────────────

def build_bob_tools(repo: Any, sess: dict) -> dict[str, Callable]:
    """Build a dictionary of callable Bob tools scoped to the current session."""

    def _check_site_scope(site_id: str) -> None:
        role = sess["role"]
        if role in ("STUDY_MANAGER", "SYSTEM_ADMIN", "AUDITOR"):
            return
        if role == "SITE_COORDINATOR" and sess.get("site_id") != site_id:
            raise PermissionError(
                f"You do not have permission to access Site {site_id}'s information. "
                f"Your access is restricted to Site {sess.get('site_id')}."
            )

    def _check_role(allowed: list[str]) -> None:
        if sess["role"] not in allowed:
            raise PermissionError(f"Your role ({sess['role']}) does not have permission to use this tool.")

    def get_trial_overview(**_) -> dict:
        _check_role(TOOL_REGISTRY["get_trial_overview"]["roles"])
        sites = repo.all("sites")
        patients = repo.all("patients")
        deviations = repo.all("deviations")
        risk_scores = repo.all("risk_scores")
        capas = repo.all("capa_records")
        high_risk = [r for r in risk_scores if r.get("risk_level") == "HIGH"]
        return {
            "total_sites": len(sites),
            "total_patients": len(patients),
            "total_deviations": len(deviations),
            "major_deviations": sum(1 for d in deviations if d["severity"] == "MAJOR"),
            "high_risk_sites": len(high_risk),
            "open_capas": sum(1 for c in capas if c["status"] in ("OPEN", "IN_PROGRESS")),
            "sources": ["Site repository", "Deviation engine", "Risk scoring service"],
        }

    def list_high_risk_sites(limit: int = 10, **_) -> dict:
        _check_role(TOOL_REGISTRY["list_high_risk_sites"]["roles"])
        risk_scores = repo.all("risk_scores")
        high = [r for r in risk_scores if r.get("risk_level") == "HIGH"]
        high.sort(key=lambda x: x["current_score"], reverse=True)
        results = []
        for r in high[:limit]:
            site = repo.find_one("sites", "site_id", r["site_id"]) or {}
            results.append({
                "site_id": r["site_id"],
                "site_name": site.get("name", r["site_id"]),
                "risk_score": r["current_score"],
                "risk_level": r["risk_level"],
                "trend": r.get("trend", "STABLE"),
                "leading_indicators": r.get("leading_indicators", []),
                "predicted_score": r.get("predicted_score", r["current_score"]),
            })
        return {
            "high_risk_sites": results,
            "count": len(results),
            "sources": ["Risk scoring service", "Deviation repository"],
        }

    def get_site_risk(site_id: str, **_) -> dict:
        _check_role(TOOL_REGISTRY["get_site_risk"]["roles"])
        _check_site_scope(site_id)
        risk = repo.find_one("risk_scores", "site_id", site_id)
        if not risk:
            raise ValueError(f"Site {site_id} not found")
        return {**risk, "sources": ["Risk scoring service", f"Site {site_id} deviation records"]}

    def explain_site_risk(site_id: str, **_) -> dict:
        _check_role(TOOL_REGISTRY["explain_site_risk"]["roles"])
        _check_site_scope(site_id)
        risk = repo.find_one("risk_scores", "site_id", site_id)
        if not risk:
            raise ValueError(f"Site {site_id} not found")
        devs = repo.find_many("deviations", "site_id", site_id)
        from collections import Counter
        type_counts = Counter(d["type"] for d in devs)
        top_types = type_counts.most_common(3)
        explanation = (
            f"Site {site_id} has a current risk score of {risk['current_score']}/100 "
            f"(risk level: {risk['risk_level']}, trend: {risk.get('trend', 'STABLE')}). "
            f"This is based on {len(devs)} deviations, "
            f"including {sum(1 for d in devs if d['severity'] == 'MAJOR')} major deviation(s). "
            f"The most frequent deviation types are: "
            f"{', '.join(f'{t.replace(chr(95), chr(32)).title()} ({c})' for t, c in top_types)}. "
            f"Leading indicators: {', '.join(risk.get('leading_indicators', ['N/A']))}."
        )
        return {
            "site_id": site_id,
            "current_score": risk["current_score"],
            "predicted_score": risk.get("predicted_score", risk["current_score"]),
            "trend": risk.get("trend", "STABLE"),
            "leading_indicators": risk.get("leading_indicators", []),
            "risk_drivers": risk.get("risk_drivers", []),
            "explanation": explanation,
            "deviation_count": len(devs),
            "major_count": sum(1 for d in devs if d["severity"] == "MAJOR"),
            "top_deviation_types": [{"type": t, "count": c} for t, c in top_types],
            "sources": ["Risk scoring service", "Deviation engine", "Protocol TG-101"],
        }

    def list_site_deviations(site_id: str, severity: str | None = None, **_) -> dict:
        _check_role(TOOL_REGISTRY["list_site_deviations"]["roles"])
        _check_site_scope(site_id)
        devs = repo.find_many("deviations", "site_id", site_id)
        if severity:
            devs = [d for d in devs if d["severity"] == severity.upper()]
        return {"site_id": site_id, "deviations": devs, "count": len(devs), "sources": ["Deviation repository"]}

    def get_deviation(deviation_id: str, **_) -> dict:
        _check_role(TOOL_REGISTRY["get_deviation"]["roles"])
        dev = repo.find_one("deviations", "deviation_id", deviation_id)
        if not dev:
            raise ValueError(f"Deviation {deviation_id} not found")
        _check_site_scope(dev["site_id"])
        return {**dev, "sources": ["Deviation repository", "Protocol TG-101"]}

    def search_protocol_rules(query: str = "", **_) -> dict:
        protocols = repo.all("protocols")
        if not protocols:
            return {"rules": [], "sources": []}
        protocol = protocols[0]
        rules = protocol.get("rules", [])
        if query:
            q = query.lower()
            rules = [r for r in rules if q in r.get("rule_id", "").lower() or q in r.get("name", "").lower() or q in r.get("domain", "").lower() or q in r.get("description", "").lower()]
        return {"protocol_id": protocol.get("protocol_id"), "rules": rules, "sources": ["Protocol repository"]}

    def compare_patient_to_protocol(patient_id: str, **_) -> dict:
        _check_role(TOOL_REGISTRY["compare_patient_to_protocol"]["roles"])
        patient = repo.find_one("patients", "patient_id", patient_id)
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")
        _check_site_scope(patient["site_id"])
        site_id = patient["site_id"]
        issues = []
        rules_checked = []

        # R-001: Age eligibility
        rules_checked.append("R-001")
        age = patient.get("age", 30)
        if not (18 <= age <= 65):
            issues.append({"rule": "R-001", "finding": f"Age {age} outside 18–65 window", "severity": "MAJOR"})

        # Load patient visits and medications for further checks
        all_visits = repo.find_many("visits", "patient_id", patient_id)
        all_meds = repo.find_many("medications", "patient_id", patient_id)
        all_site_devs = repo.find_many("deviations", "site_id", site_id)
        patient_devs = [d for d in all_site_devs if d.get("patient_id") == patient_id]

        # R-003: Dosing — check visits for incorrect doses
        rules_checked.append("R-003")
        for v in all_visits:
            if v.get("dose_actual") and v.get("dose_expected") and v["dose_actual"] != v["dose_expected"]:
                issues.append({
                    "rule": "R-003",
                    "finding": f"Incorrect dose at visit {v.get('visit_number', '?')}: expected {v['dose_expected']}mg, got {v['dose_actual']}mg",
                    "severity": "MAJOR",
                })

        # R-004: Prohibited medications
        rules_checked.append("R-004")
        prohibited_names = {"Drug X", "Drug Y"}
        for med in all_meds:
            if med.get("medication_name") in prohibited_names:
                issues.append({
                    "rule": "R-004",
                    "finding": f"Prohibited medication: {med['medication_name']}",
                    "severity": "MAJOR",
                })

        # R-005: Missing assessments — check visits
        rules_checked.append("R-005")
        for v in all_visits:
            if v.get("assessment_status") == "MISSING":
                issues.append({
                    "rule": "R-005",
                    "finding": f"Missing safety assessment at visit {v.get('visit_number', '?')} on {v.get('actual_date', '?')}",
                    "severity": "MAJOR",
                })

        # R-006: Late data entry
        rules_checked.append("R-006")
        from datetime import datetime as _dt
        for v in all_visits:
            try:
                vd = _dt.strptime(v["actual_date"], "%Y-%m-%d").date()
                ed = _dt.strptime(v["data_entry_date"], "%Y-%m-%d").date()
                delay = (ed - vd).days
                if delay > 2:
                    issues.append({
                        "rule": "R-006",
                        "finding": f"Data entered {delay} days after visit {v.get('visit_number', '?')} (limit: 2 days)",
                        "severity": "ADMINISTRATIVE",
                    })
            except (KeyError, ValueError, TypeError):
                pass

        # R-002 / R-007: Visit windows (visit 2 = Day 7 ± 2, visit 3 = Day 14 ± 2)
        rules_checked.extend(["R-002", "R-007"])
        window_rules = {2: ("R-002", 7, 2), 3: ("R-007", 14, 2)}
        from datetime import date as _date
        enroll = _date(2026, 1, 15)
        for v in all_visits:
            vnum = v.get("visit_number")
            if vnum in window_rules:
                rule_id, day_offset, tolerance = window_rules[vnum]
                try:
                    actual = _dt.strptime(v["actual_date"], "%Y-%m-%d").date()
                    scheduled = enroll + __import__("datetime").timedelta(days=day_offset)
                    diff = abs((actual - scheduled).days)
                    if diff > tolerance:
                        issues.append({
                            "rule": rule_id,
                            "finding": f"Visit {vnum} occurred {diff} days outside ±{tolerance}-day window",
                            "severity": "MINOR",
                        })
                except (KeyError, ValueError, TypeError):
                    pass

        # R-008: Missed visits — all 5 visits should exist
        rules_checked.append("R-008")
        recorded_visits = {v.get("visit_number") for v in all_visits}
        for vnum in range(1, 6):
            if vnum not in recorded_visits:
                issues.append({
                    "rule": "R-008",
                    "finding": f"Visit {vnum} not recorded for patient",
                    "severity": "MINOR",
                })

        passed = len(rules_checked) - len({i["rule"] for i in issues})
        return {
            "patient_id": patient_id,
            "site_id": site_id,
            "rules_checked": rules_checked,
            "issues": issues,
            "passed": max(0, passed),
            "failed": len({i["rule"] for i in issues}),
            "compliant": len(issues) == 0,
            "sources": ["Patient repository", "Visit repository", "Medication repository", "Protocol TG-101"],
        }

    def get_site_trends(site_id: str, **_) -> dict:
        _check_role(TOOL_REGISTRY["get_site_trends"]["roles"])
        _check_site_scope(site_id)
        risk = repo.find_one("risk_scores", "site_id", site_id) or {}
        devs = repo.find_many("deviations", "site_id", site_id)
        from collections import Counter
        return {
            "site_id": site_id,
            "trend": risk.get("trend", "STABLE"),
            "sparkline": risk.get("sparkline", []),
            "current_score": risk.get("current_score", 0),
            "predicted_score": risk.get("predicted_score", 0),
            "deviation_type_breakdown": dict(Counter(d["type"] for d in devs)),
            "sources": ["Risk scoring service", "Deviation repository"],
        }

    def recommend_site_actions(site_id: str, **_) -> dict:
        _check_role(TOOL_REGISTRY["recommend_site_actions"]["roles"])
        _check_site_scope(site_id)
        devs = repo.find_many("deviations", "site_id", site_id)
        risk = repo.find_one("risk_scores", "site_id", site_id) or {}
        from collections import Counter
        from services import _corrective_actions, _preventive_actions
        type_counts = Counter(d["type"] for d in devs)
        dominant = type_counts.most_common(1)[0][0] if type_counts else "UNKNOWN"
        return {
            "site_id": site_id,
            "risk_level": risk.get("risk_level", "UNKNOWN"),
            "dominant_deviation_type": dominant,
            "corrective_actions": _corrective_actions(dominant)[:3],
            "preventive_actions": _preventive_actions(dominant)[:3],
            "disclaimer": "AI-generated suggestions. Qualified clinical review required.",
            "sources": ["Deviation repository", "Risk engine", "CAPA service"],
        }

    def generate_capa(site_id: str, **_) -> dict:
        _check_role(TOOL_REGISTRY["generate_capa"]["roles"])
        _check_site_scope(site_id)
        devs = repo.find_many("deviations", "site_id", site_id)
        major_devs = [d for d in devs if d["severity"] == "MAJOR"][:5]
        from services import generate_capa_record
        record = generate_capa_record(site_id, major_devs, sess["user_id"])
        return {**record, "sources": ["Deviation repository", "CAPA service", "Risk engine"]}

    def get_capa_status(site_id: str | None = None, **_) -> dict:
        _check_role(TOOL_REGISTRY["get_capa_status"]["roles"])
        capas = repo.all("capa_records")
        if site_id:
            _check_site_scope(site_id)
            capas = [c for c in capas if c["site_id"] == site_id]
        elif sess["role"] == "SITE_COORDINATOR":
            capas = [c for c in capas if c["site_id"] == sess["site_id"]]
        from collections import Counter
        return {
            "capa_records": capas,
            "status_summary": dict(Counter(c["status"] for c in capas)),
            "sources": ["CAPA repository"],
        }

    def generate_risk_report(site_id: str, **_) -> dict:
        _check_role(TOOL_REGISTRY["generate_risk_report"]["roles"])
        _check_site_scope(site_id)
        site = repo.find_one("sites", "site_id", site_id) or {}
        risk = repo.find_one("risk_scores", "site_id", site_id) or {}
        devs = repo.find_many("deviations", "site_id", site_id)
        capas = [c for c in repo.all("capa_records") if c["site_id"] == site_id]
        from datetime import datetime, timezone
        return {
            "report_type": "site_risk",
            "site": site,
            "risk": risk,
            "total_deviations": len(devs),
            "major_deviations": sum(1 for d in devs if d["severity"] == "MAJOR"),
            "open_capas": sum(1 for c in capas if c["status"] in ("OPEN", "IN_PROGRESS")),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": ["Site repository", "Risk engine", "Deviation repository", "CAPA service"],
            "disclaimer": "Synthetic data. Not for clinical or regulatory use.",
        }

    def get_site_risk_history(site_id: str, **_) -> dict:
        _check_role(TOOL_REGISTRY["get_site_risk_history"]["roles"])
        _check_site_scope(site_id)
        history = [h for h in repo.all("risk_history") if h.get("site_id") == site_id]
        history.sort(key=lambda h: h.get("period", ""))
        return {
            "site_id": site_id,
            "history": history,
            "period_count": len(history),
            "sources": ["Risk history repository"],
        }

    def analyze_deviation_pattern(site_id: str, **_) -> dict:
        _check_role(TOOL_REGISTRY["analyze_deviation_pattern"]["roles"])
        _check_site_scope(site_id)
        devs = repo.find_many("deviations", "site_id", site_id)
        patients = repo.find_many("patients", "site_id", site_id)
        from services import analyze_deviation_pattern as _svc_pattern
        result = _svc_pattern(site_id, devs, patients)
        return {**result, "sources": ["Deviation repository"]}

    def get_affected_patients(site_id: str, deviation_type: str, **_) -> dict:
        _check_role(TOOL_REGISTRY["get_affected_patients"]["roles"])
        _check_site_scope(site_id)
        devs = repo.find_many("deviations", "site_id", site_id)
        matching = [d for d in devs if d.get("type") == deviation_type]
        patient_ids = list({d.get("patient_id") for d in matching if d.get("patient_id")})
        patients = [repo.find_one("patients", "patient_id", pid) for pid in patient_ids]
        patients = [p for p in patients if p]
        return {
            "site_id": site_id,
            "deviation_type": deviation_type,
            "affected_patient_count": len(patient_ids),
            "deviation_count": len(matching),
            "patients": [{"patient_id": p["patient_id"], "age": p.get("age"), "status": p.get("status")} for p in patients],
            "sources": ["Deviation repository", "Patient repository"],
        }

    return {
        "get_trial_overview": get_trial_overview,
        "list_high_risk_sites": list_high_risk_sites,
        "get_site_risk": get_site_risk,
        "explain_site_risk": explain_site_risk,
        "list_site_deviations": list_site_deviations,
        "get_deviation": get_deviation,
        "search_protocol_rules": search_protocol_rules,
        "compare_patient_to_protocol": compare_patient_to_protocol,
        "get_site_trends": get_site_trends,
        "recommend_site_actions": recommend_site_actions,
        "generate_capa": generate_capa,
        "get_capa_status": get_capa_status,
        "generate_risk_report": generate_risk_report,
        "get_site_risk_history": get_site_risk_history,
        "analyze_deviation_pattern": analyze_deviation_pattern,
        "get_affected_patients": get_affected_patients,
    }


# ─── Bob provider boundary ────────────────────────────────────────────────────

class LocalDemoBobProvider:
    """
    LOCAL DEMO ADAPTER — NOT IBM BOB.

    This adapter provides deterministic, evidence-backed natural-language responses
    by calling the same MCP-ready tool contracts that a real IBM Bob integration would use.

    Architecture:
        Browser → server.py → LocalDemoBobProvider → build_bob_tools() → MongoDB

    For real IBM Bob integration, see src/mcp_server.py and .bob/mcp.json.
    """
    name = "DEMO BOB ADAPTER (not IBM Bob)"

    # ── Intent categories ────────────────────────────────────────────────────
    # Each entry: (required_context_keywords, trigger_keywords, intent)
    # required_context_keywords: at least one must be present (trial domain signal)
    # trigger_keywords: at least one must be present (action signal)
    # Both conditions must be met for the intent to fire.
    #
    # UNSUPPORTED fires when NO intent matches.

    _INTENT_RULES = [
        # ── More-specific rules first ──────────────────────────────────────
        # NOTE: COMPARE_SITES is NOT in this list.  It is handled entirely by
        # the explicit two-site shortcut in answer() (step 2b) before
        # _classify_intent() is ever called.  Having it here caused false
        # positives when a single-site message contained words like "worse".

        # SITE RISK EXPLANATION: "why is S037 high risk?" — requires why/explain + risk/site
        # Must come before HIGH_RISK_SITES to avoid "why … high risk" being swallowed there
        {
            "intent": "SITE_RISK_EXPLANATION",
            "tool": "explain_site_risk",
            "context": ["site", "risk", "s0"],
            "trigger": ["why", "explain", "reason", "driver", "what makes", "what is causing", "what caused", "contributing"],
        },
        # TRIAL_OVERVIEW: must mention trial/clinical/trialguard/study + overview/summary/total
        {
            "intent": "TRIAL_OVERVIEW",
            "tool": "get_trial_overview",
            "context": ["trial", "clinical", "trialguard", "study"],
            "trigger": ["overview", "summary", "summarize", "total", "how many", "status", "all sites", "all patients"],
        },
        # HIGH_RISK_SITES: "which sites are high risk?" — requires explicit plural sites/which sites
        # context: "sites" plural OR "which" (not matched by single-site questions)
        {
            "intent": "HIGH_RISK_SITES",
            "tool": "list_high_risk_sites",
            "context": ["sites", "which site", "all site"],
            "trigger": ["highest risk", "high risk", "most at risk", "riskiest", "highest", "ranked", "top sites", "worst sites", "at risk"],
        },
        # RISK REPORT: must mention report keyword explicitly — before CAPA_GENERATION
        # to prevent "generate a risk report" matching CAPA
        {
            "intent": "RISK_REPORT",
            "tool": "generate_risk_report",
            "context": ["report", "risk report", "site report"],
            "trigger": ["report", "generate report", "create report", "risk report"],
        },
        # CAPA GENERATION: must mention capa/corrective/preventive + generate/create/draft
        {
            "intent": "CAPA_GENERATION",
            "tool": "generate_capa",
            "context": ["capa", "corrective", "preventive"],
            "trigger": ["generate", "create", "draft", "write", "open", "new", "capa"],
        },
        # CAPA STATUS: must mention capa + status/progress/open/closed/list
        {
            "intent": "CAPA_STATUS",
            "tool": "get_capa_status",
            "context": ["capa"],
            "trigger": ["status", "progress", "open capas", "closed", "existing", "list capas", "all capas", "capa records"],
        },
        # SITE TRENDS: must mention site/risk/deviation + trend/trajectory/worsening
        {
            "intent": "SITE_TRENDS",
            "tool": "get_site_trends",
            "context": ["site", "risk", "deviation", "s0"],
            "trigger": ["trend", "trajectory", "isolated", "getting worse", "worsening", "improving", "sparkline", "pattern over time", "over time", "getting better"],
        },
        # SITE ACTIONS: must mention site/risk/deviation + recommend/actions
        {
            "intent": "SITE_ACTIONS",
            "tool": "recommend_site_actions",
            "context": ["site", "risk", "deviation", "s0"],
            "trigger": ["recommend", "what should we do", "what to do", "actions", "what can we", "suggestions", "intervention", "next steps", "corrective", "action plan"],
        },
        # SITE DEVIATIONS: must mention deviation/protocol/violation + list/show/deviations
        {
            "intent": "SITE_DEVIATIONS",
            "tool": "list_site_deviations",
            "context": ["deviation", "deviations", "protocol violation", "violation", "finding"],
            "trigger": ["list", "show", "what", "which", "all", "major", "deviations", "violations", "findings", "contributing"],
        },
        # SITE RISK SCORE: must mention site + risk score/level/current/assessment
        {
            "intent": "SITE_RISK",
            "tool": "get_site_risk",
            "context": ["site", "risk", "s0"],
            "trigger": ["risk score", "risk level", "current risk", "score", "how risky", "risk assessment", "risk status"],
        },
        # PROTOCOL RULES: must mention protocol/rule/requirement + search/find/show/list
        {
            "intent": "PROTOCOL_RULES",
            "tool": "search_protocol_rules",
            "context": ["protocol", "rule", "requirement", "tg-101", "tg101"],
            "trigger": ["search", "find", "show", "list", "what", "which", "rule", "rules", "requirement"],
        },
        # PATIENT PROTOCOL: must mention patient + check/compare/eligibility
        {
            "intent": "PATIENT_PROTOCOL",
            "tool": "compare_patient_to_protocol",
            "context": ["patient"],
            "trigger": ["check", "compare", "eligible", "eligibility", "compliant", "compliance", "violation", "meets criteria"],
        },
        # RISK HISTORY: must mention site/risk/history + history/trend/over time/periods
        {
            "intent": "RISK_HISTORY",
            "tool": "get_site_risk_history",
            "context": ["site", "risk", "s0"],
            "trigger": ["history", "historical", "over time", "periods", "snapshots", "past scores", "trend history"],
        },
        # DEVIATION PATTERN: must mention site/deviation/pattern + pattern/recurring/recurrence
        {
            "intent": "DEVIATION_PATTERN",
            "tool": "analyze_deviation_pattern",
            "context": ["site", "deviation", "pattern", "s0"],
            "trigger": ["pattern", "recurring", "recurrence", "repeat", "same type", "how often", "frequency", "spread"],
        },
        # AFFECTED PATIENTS: must mention patient/site + affected/impacted/which patients
        {
            "intent": "AFFECTED_PATIENTS",
            "tool": "get_affected_patients",
            "context": ["patient", "patients", "deviation", "site"],
            "trigger": ["affected", "impacted", "which patients", "who", "involved patients", "patients with", "patient list"],
        },
    ]

    # Phrases that are clear non-clinical / greeting signals
    _NON_CLINICAL_TRIGGERS = [
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
        "how are you", "what's up", "howdy", "greetings", "tell me a joke",
        "joke", "weather", "what is the weather", "what time is it",
        "who are you", "what is your name", "your name",
        "thanks", "thank you", "cheers", "bye", "goodbye",
        "help me with", "help", "random",
        "test", "abc",
    ]

    _UNSUPPORTED_RESPONSE = (
        "I can help with TrialGuard clinical-trial risk monitoring. "
        "Try asking about:\n\n"
        "• Trial overview: \"Give me a summary of the trial\"\n"
        "• Site risk: \"Why is Site S037 high risk?\"\n"
        "• High-risk sites: \"Which sites have the highest risk?\"\n"
        "• Deviations: \"Show me deviations at Site S037\"\n"
        "• Trends: \"Is Site S037's risk getting worse?\"\n"
        "• Actions: \"What actions are recommended for S037?\"\n"
        "• CAPA: \"Generate a CAPA for Site S037\"\n"
        "• Risk report: \"Generate a risk report for S037\""
    )

    def _classify_intent(self, lowered: str, has_site: bool) -> str | None:
        """
        Return the matching intent name, or None if no TrialGuard intent is detected.

        Rules:
        1. If the message is a clear non-clinical phrase, return None immediately.
        2. Otherwise scan intent rules: both a context keyword AND a trigger keyword
           must appear in the lowered message for the intent to fire.
        3. If no rule fires, return None.
        """
        import re as _re
        # Check for explicit non-clinical / greeting signals using word boundaries
        for phrase in self._NON_CLINICAL_TRIGGERS:
            # Build a word-boundary pattern for the phrase
            pattern = r'(?<!\w)' + _re.escape(phrase) + r'(?!\w)'
            if _re.search(pattern, lowered):
                # Extra guard: even if a greeting word appears, allow the message
                # if it also contains a clear TrialGuard clinical signal
                if has_site and any(kw in lowered for kw in ["risk", "deviation", "capa", "trend", "explain", "why"]):
                    break  # let normal routing handle it
                # Allow if the message has strong clinical context beyond the greeting
                if any(kw in lowered for kw in ["trial", "clinical", "protocol", "site", "capa", "deviation"]):
                    break  # let normal routing handle it
                return None

        # Check intent rules in order
        for rule in self._INTENT_RULES:
            context_match = any(kw in lowered for kw in rule["context"])
            trigger_match = any(kw in lowered for kw in rule["trigger"])
            # Site ID in message counts as context for site-scoped intents
            if has_site and rule["intent"] in (
                "SITE_RISK", "SITE_RISK_EXPLANATION", "SITE_TRENDS",
                "SITE_ACTIONS", "SITE_DEVIATIONS", "CAPA_GENERATION",
                "RISK_REPORT", "RISK_HISTORY", "DEVIATION_PATTERN", "AFFECTED_PATIENTS",
            ):
                context_match = context_match or True
            if context_match and trigger_match:
                return rule["intent"]

        return None

    def _tool_for_intent(self, intent: str) -> str:
        for rule in self._INTENT_RULES:
            if rule["intent"] == intent:
                return rule["tool"]
        return ""

    def answer(self, question: str, user: User, tools: dict[str, Callable]) -> dict:
        import re
        lowered = question.lower().strip()

        # ── 1. Extract site ID from message ──────────────────────────────────
        site_matches = re.findall(r'\bS\d{3}\b', question)
        # Use site from message, or the user's own assigned site (never default to S037)
        target_site = site_matches[0] if site_matches else user.site_id

        # ── 2. Permission check: site coordinator cross-site access ──────────
        if user.role == "SITE_COORDINATOR":
            for mentioned in site_matches:
                if mentioned != user.site_id:
                    return {
                        "answer": (
                            f"You do not have permission to access Site {mentioned}'s information. "
                            f"Your access is restricted to Site {user.site_id}."
                        ),
                        "sources": [],
                        "provider": self.name,
                        "tool_result": None,
                        "tool_used": None,
                    }

        # ── 2b. COMPARE_SITES shortcut — two site IDs present ────────────────
        # Detect before normal intent classification so "S001 vs S032" is never
        # reduced to a single-site report.
        if len(site_matches) >= 2:
            compare_triggers = ["compare", "vs", "versus", "comparison", "difference",
                                 "which is", "riskier", "better", "worse", "between",
                                 "report", "generate"]
            if any(kw in lowered for kw in compare_triggers):
                site_a, site_b = site_matches[0], site_matches[1]
                return self._handle_compare(site_a, site_b, tools, user)

        # ── 3. Classify intent ───────────────────────────────────────────────
        intent = self._classify_intent(lowered, has_site=bool(site_matches))

        if intent is None:
            # No TrialGuard intent detected — return unsupported response
            return {
                "answer": self._UNSUPPORTED_RESPONSE,
                "sources": [],
                "provider": self.name,
                "tool_result": None,
                "tool_used": None,
            }

        tool_name = self._tool_for_intent(intent)

        # ── 4. Role-based tool downgrade ─────────────────────────────────────
        if tool_name in ("generate_capa", "recommend_site_actions") and user.role == "AUDITOR":
            # Auditor cannot generate CAPAs or recommendations — show risk explanation instead
            if target_site:
                tool_name = "explain_site_risk"
            else:
                return {
                    "answer": "As an Auditor, you can view risk data but not generate CAPA or recommendations. "
                              "Ask about a specific site's risk, deviations, or the trial overview.",
                    "sources": [],
                    "provider": self.name,
                    "tool_result": None,
                    "tool_used": None,
                }
        if tool_name in ("list_high_risk_sites", "get_trial_overview") and user.role == "SITE_COORDINATOR":
            # Coordinator can't query all sites — redirect to their own site
            if user.site_id:
                tool_name = "explain_site_risk"
                target_site = user.site_id
            else:
                return {
                    "answer": "Your account is not assigned to a specific site. Please contact your administrator.",
                    "sources": [],
                    "provider": self.name,
                    "tool_result": None,
                    "tool_used": None,
                }
        if tool_name in ("generate_capa", "recommend_site_actions") and user.role == "SITE_COORDINATOR":
            # Coordinator can't generate CAPAs — redirect to site risk
            if target_site:
                tool_name = "explain_site_risk"
            else:
                return {
                    "answer": "As a Site Coordinator, you can view your site's risk but not generate CAPA or recommendations.",
                    "sources": [],
                    "provider": self.name,
                    "tool_result": None,
                    "tool_used": None,
                }

        # ── 5. For site-scoped tools, require a site ID ──────────────────────
        _site_scoped = {
            "get_site_risk", "explain_site_risk", "list_site_deviations",
            "get_site_trends", "recommend_site_actions", "generate_capa",
            "generate_risk_report", "get_site_risk_history", "analyze_deviation_pattern",
        }
        if tool_name in _site_scoped and not target_site:
            return {
                "answer": (
                    "Please specify a site ID (e.g. S037) in your question. "
                    "For example: \"Why is Site S037 high risk?\""
                ),
                "sources": [],
                "provider": self.name,
                "tool_result": None,
                "tool_used": tool_name,
            }

        # ── 6. Call tool ──────────────────────────────────────────────────────
        try:
            fn = tools.get(tool_name)
            if not fn:
                return {
                    "answer": "That tool is not available in the current configuration.",
                    "sources": [],
                    "provider": self.name,
                    "tool_result": None,
                    "tool_used": tool_name,
                }

            if tool_name in _site_scoped:
                result = fn(site_id=target_site)
            elif tool_name == "list_high_risk_sites":
                result = fn()
            elif tool_name == "get_trial_overview":
                result = fn()
            elif tool_name == "get_capa_status":
                result = fn(site_id=target_site) if target_site else fn()
            elif tool_name == "search_protocol_rules":
                # Extract a specific rule ID (e.g. R-001) if present; otherwise pass
                # a keyword from the question so the filter is narrowly scoped.
                rule_id_match = re.search(r'\bR-\d+\b', question, re.IGNORECASE)
                if rule_id_match:
                    query_str = rule_id_match.group(0).upper()
                else:
                    # Strip common filler words and use what remains as the keyword
                    filler = re.compile(
                        r'\b(what|is|the|protocol|rule|tell|me|about|describe|show|rules|for|a|an)\b',
                        re.IGNORECASE,
                    )
                    query_str = filler.sub("", question).strip()
                result = fn(query=query_str)
            elif tool_name == "compare_patient_to_protocol":
                # patient_id must be in the message — extract P-XXXXX pattern
                patient_matches = re.findall(r'\bP-?\d+\b', question, re.IGNORECASE)
                if not patient_matches:
                    return {
                        "answer": "Please include a patient ID (e.g. P-001) in your question.",
                        "sources": [],
                        "provider": self.name,
                        "tool_result": None,
                        "tool_used": tool_name,
                    }
                result = fn(patient_id=patient_matches[0])
            elif tool_name == "get_affected_patients":
                # Need site_id + deviation_type: try to extract type from question
                dev_types = ["INCORRECT_DOSE", "MISSED_VISIT", "PROHIBITED_MEDICATION",
                             "MISSING_ASSESSMENT", "LATE_DATA_ENTRY", "VISIT_OUTSIDE_WINDOW",
                             "ELIGIBILITY_VIOLATION"]
                found_type = None
                for dt in dev_types:
                    if dt.lower().replace("_", " ") in lowered or dt.lower() in lowered:
                        found_type = dt
                        break
                if not found_type and "dose" in lowered:
                    found_type = "INCORRECT_DOSE"
                elif not found_type and ("missed" in lowered or "visit" in lowered):
                    found_type = "MISSED_VISIT"
                elif not found_type:
                    found_type = "INCORRECT_DOSE"  # default
                result = fn(site_id=target_site, deviation_type=found_type) if target_site else fn(site_id="S037", deviation_type=found_type)
            else:
                result = fn(site_id=target_site) if target_site else fn()

            answer = self._compose_answer(tool_name, result, target_site or "", question, user)
            sources = result.pop("sources", ["Risk engine", "Deviation repository", "Protocol TG-101"])

            return {
                "answer": answer,
                "sources": sources,
                "provider": self.name,
                "tool_result": result,
                "tool_used": tool_name,
                "disclaimer": "Responses are generated from synthetic data for demonstration only.",
            }

        except PermissionError as e:
            return {"answer": str(e), "sources": [], "provider": self.name, "tool_result": None, "tool_used": tool_name}
        except Exception as e:
            return {
                "answer": f"Unable to process that request: {e}",
                "sources": [],
                "provider": self.name,
                "tool_result": None,
                "tool_used": tool_name,
            }

    def _handle_compare(self, site_a: str, site_b: str, tools: dict, user: User) -> dict:
        """Call risk + trends + deviations for both sites and compose a side-by-side comparison."""
        try:
            fn_risk   = tools.get("get_site_risk")
            fn_trends = tools.get("get_site_trends")
            fn_devs   = tools.get("list_site_deviations")

            risk_a   = fn_risk(site_id=site_a)   if fn_risk   else {}
            risk_b   = fn_risk(site_id=site_b)   if fn_risk   else {}
            trend_a  = fn_trends(site_id=site_a) if fn_trends else {}
            trend_b  = fn_trends(site_id=site_b) if fn_trends else {}
            devs_a   = fn_devs(site_id=site_a)   if fn_devs   else {"deviations": [], "count": 0}
            devs_b   = fn_devs(site_id=site_b)   if fn_devs   else {"deviations": [], "count": 0}

            maj_a = sum(1 for d in devs_a.get("deviations", []) if d.get("severity") == "MAJOR")
            maj_b = sum(1 for d in devs_b.get("deviations", []) if d.get("severity") == "MAJOR")

            answer = self._compose_compare(
                site_a, site_b,
                risk_a, risk_b,
                trend_a, trend_b,
                devs_a["count"], devs_b["count"],
                maj_a, maj_b,
            )
            sources = ["Risk scoring service", "Deviation repository", "Site repository"]
            return {
                "answer": answer,
                "sources": sources,
                "provider": self.name,
                "tool_result": {"site_a": site_a, "site_b": site_b},
                "tool_used": "compare_sites",
                "disclaimer": "Responses are generated from synthetic data for demonstration only.",
            }
        except PermissionError as e:
            return {"answer": str(e), "sources": [], "provider": self.name, "tool_result": None, "tool_used": "compare_sites"}
        except Exception as e:
            return {"answer": f"Unable to compare sites: {e}", "sources": [], "provider": self.name, "tool_result": None, "tool_used": "compare_sites"}

    def _compose_compare(
        self,
        site_a: str, site_b: str,
        risk_a: dict, risk_b: dict,
        trend_a: dict, trend_b: dict,
        total_a: int, total_b: int,
        major_a: int, major_b: int,
    ) -> str:
        score_a  = risk_a.get("current_score", 0)
        score_b  = risk_b.get("current_score", 0)
        level_a  = risk_a.get("risk_level", "?")
        level_b  = risk_b.get("risk_level", "?")
        trend_a_ = risk_a.get("trend", "STABLE")
        trend_b_ = risk_b.get("trend", "STABLE")
        pred_a   = trend_a.get("predicted_score", score_a)
        pred_b   = trend_b.get("predicted_score", score_b)
        ind_a    = risk_a.get("leading_indicators", [])
        ind_b    = risk_b.get("leading_indicators", [])

        lines = [
            f"Comparison Report: {site_a} vs {site_b}",
            f"{'-' * 48}",
            f"{'Metric':<28} {site_a:>8}  {site_b:>8}",
            f"{'-' * 48}",
            f"{'Risk score':<28} {score_a:>7}/100  {score_b:>7}/100",
            f"{'Risk level':<28} {level_a:>8}  {level_b:>8}",
            f"{'Trend':<28} {trend_a_:>8}  {trend_b_:>8}",
            f"{'Predicted score':<28} {pred_a:>7}/100  {pred_b:>7}/100",
            f"{'Total deviations':<28} {total_a:>8}  {total_b:>8}",
            f"{'Major deviations':<28} {major_a:>8}  {major_b:>8}",
            f"{'-' * 48}",
        ]

        # Verdict
        if score_a > score_b:
            higher, lower = site_a, site_b
            diff = score_a - score_b
        elif score_b > score_a:
            higher, lower = site_b, site_a
            diff = score_b - score_a
        else:
            higher = lower = None
            diff = 0

        if higher:
            lines.append(f"\nVerdict: {higher} is at higher risk ({diff} points above {lower}).")
        else:
            lines.append(f"\nVerdict: Both sites have the same risk score.")

        # Trend warning
        both_worsening = trend_a_ == "WORSENING" and trend_b_ == "WORSENING"
        if both_worsening:
            lines.append(f"Both sites show a WORSENING trend - escalated monitoring recommended for both.")
        elif trend_a_ == "WORSENING":
            lines.append(f"{site_a} is on a worsening trajectory; {site_b} is {trend_b_}.")
        elif trend_b_ == "WORSENING":
            lines.append(f"{site_b} is on a worsening trajectory; {site_a} is {trend_a_}.")

        # Leading indicators
        if ind_a:
            lines.append(f"\n{site_a} leading indicators: {', '.join(ind_a[:3])}.")
        if ind_b:
            lines.append(f"{site_b} leading indicators: {', '.join(ind_b[:3])}.")

        lines.append(f"\nData source: TrialGuard MongoDB - risk engine, deviation repository.")
        return "\n".join(lines)

    def _compose_answer(self, tool_name: str, result: dict, site_id: str, question: str, user: User) -> str:
        if tool_name == "list_high_risk_sites":
            sites = result.get("high_risk_sites", [])
            if not sites:
                return "No high-risk sites found in the current dataset."
            top = sites[0]
            lines = [f"There are {len(sites)} high-risk site(s) in the current trial dataset."]
            lines.append(f"\nThe highest-risk site is {top['site_id']} ({top.get('site_name', '')}) "
                         f"with a risk score of {top['risk_score']}/100 and a {top['trend']} trend.")
            if len(sites) > 1:
                lines.append("\nOther high-risk sites:")
                for s in sites[1:5]:
                    lines.append(f"  • {s['site_id']}: {s['risk_score']}/100 ({s['trend']})")
            if top.get("leading_indicators"):
                lines.append(f"\nLeading indicators at {top['site_id']}: {', '.join(top['leading_indicators'][:3])}.")
            return "\n".join(lines)

        elif tool_name in ("explain_site_risk", "get_site_risk"):
            exp = result.get("explanation") or (
                f"Site {site_id} has a risk score of {result.get('current_score', '?')}/100. "
                f"Trend: {result.get('trend', 'STABLE')}. "
                f"Leading indicators: {', '.join(result.get('leading_indicators', []) or ['N/A'])}."
            )
            predicted = result.get("predicted_score")
            if predicted and predicted != result.get("current_score"):
                exp += f"\n\nProjected score for the next monitoring period: {predicted}/100. "
                if predicted > result.get("current_score", 0):
                    exp += f"⚠ Site {site_id} is projected to enter higher risk territory."
            return exp

        elif tool_name == "generate_capa":
            return (
                f"CAPA {result.get('capa_id', 'draft')} has been generated for Site {site_id}.\n\n"
                f"Problem: {result.get('problem_statement', '')}\n\n"
                f"Root Cause (AI hypothesis - requires qualified review): {result.get('root_cause', '')}\n\n"
                f"Priority: {result.get('priority', 'MEDIUM')} | Due: {result.get('due_date', 'TBD')}\n\n"
                f"⚠ {result.get('disclaimer', 'Qualified review required before implementation.')}"
            )

        elif tool_name == "recommend_site_actions":
            corrections = result.get("corrective_actions", [])
            preventions = result.get("preventive_actions", [])
            return (
                f"Recommended actions for Site {site_id} "
                f"(dominant issue: {result.get('dominant_deviation_type', 'Unknown').replace('_', ' ').title()}):\n\n"
                f"Corrective actions:\n" +
                "\n".join(f"  {i+1}. {a}" for i, a in enumerate(corrections)) +
                f"\n\nPreventive actions:\n" +
                "\n".join(f"  {i+1}. {a}" for i, a in enumerate(preventions)) +
                f"\n\n⚠ {result.get('disclaimer', 'Qualified review required.')}"
            )

        elif tool_name == "get_site_trends":
            trend = result.get("trend", "STABLE")
            current = result.get("current_score", 0)
            predicted = result.get("predicted_score", current)
            types = result.get("deviation_type_breakdown", {})
            answer = (
                f"Site {site_id} trend analysis:\n\n"
                f"Current risk score: {current}/100 → Predicted: {predicted}/100\n"
                f"Trend: {trend}\n\n"
            )
            if trend == "WORSENING":
                answer += f"⚠ Site {site_id} is on a worsening trajectory. "
                answer += "This does not appear to be an isolated incident — deviation frequency is increasing over recent monitoring periods."
            elif trend == "IMPROVING":
                answer += f"Site {site_id} shows improvement. Current interventions appear to be effective."
            else:
                answer += f"Site {site_id} is in a stable pattern."
            if types:
                top = sorted(types.items(), key=lambda x: -x[1])[:3]
                answer += f"\n\nTop deviation types: " + ", ".join(f"{t.replace('_', ' ').title()} ({c})" for t, c in top)
            return answer

        elif tool_name == "get_trial_overview":
            return (
                f"Trial summary:\n\n"
                f"• Total sites: {result.get('total_sites', '?')}\n"
                f"• Total patients (synthetic): {result.get('total_patients', '?')}\n"
                f"• Total deviations: {result.get('total_deviations', '?')}\n"
                f"• Major deviations: {result.get('major_deviations', '?')}\n"
                f"• High-risk sites: {result.get('high_risk_sites', '?')}\n"
                f"• Open CAPAs: {result.get('open_capas', '?')}\n\n"
                f"All data is synthetic and for demonstration only."
            )

        elif tool_name == "generate_risk_report":
            return (
                f"Risk report for Site {site_id} generated.\n\n"
                f"Risk score: {result.get('risk', {}).get('current_score', '?')}/100 "
                f"({result.get('risk', {}).get('risk_level', '?')})\n"
                f"Total deviations: {result.get('total_deviations', '?')}\n"
                f"Major deviations: {result.get('major_deviations', '?')}\n"
                f"Open CAPAs: {result.get('open_capas', '?')}\n\n"
                f"Use the Reports section to download a full formatted report."
            )

        elif tool_name == "search_protocol_rules":
            rules = result.get("rules", [])
            pid = result.get("protocol_id", "TG-101")
            if not rules:
                return f"No matching protocol rules found in {pid}."
            lines = [f"Protocol {pid} — {len(rules)} rule(s) found:\n"]
            for r in rules:
                lines.append(
                    f"Rule {r.get('rule_id', '?')} — {r.get('name', '')}\n"
                    f"  Domain: {r.get('domain', '')}\n"
                    f"  Requirement: {r.get('expected', '')}\n"
                    f"  Description: {r.get('description', '')}\n"
                    f"  Severity if violated: {r.get('severity_if_violated', '?')}\n"
                )
            return "\n".join(lines)

        elif tool_name == "list_site_deviations":
            devs = result.get("deviations", [])
            count = result.get("count", len(devs))
            sid = result.get("site_id", site_id)
            if not devs:
                return f"No deviations found for Site {sid}."
            lines = [f"Site {sid} — {count} deviation(s):\n"]
            for d in devs[:10]:
                lines.append(
                    f"• [{d.get('severity', '?')}] {d.get('type', '?').replace('_', ' ').title()} "
                    f"(ID: {d.get('deviation_id', '?')}) — detected {d.get('detected_at', '?')}"
                )
            if count > 10:
                lines.append(f"… and {count - 10} more. Use the Deviations page for the full list.")
            return "\n".join(lines)

        elif tool_name == "get_deviation":
            dev_id = result.get("deviation_id", "?")
            return (
                f"Deviation {dev_id}\n\n"
                f"Site: {result.get('site_id', '?')}\n"
                f"Type: {result.get('type', '?').replace('_', ' ').title()}\n"
                f"Severity: {result.get('severity', '?')}\n"
                f"Detected: {result.get('detected_at', '?')}\n"
                f"Description: {result.get('description', result.get('evidence', ''))}"
            )

        elif tool_name == "compare_patient_to_protocol":
            pid = result.get("patient_id", "?")
            compliant = result.get("compliant", True)
            issues = result.get("issues", [])
            rules_checked = result.get("rules_checked", [])
            passed = result.get("passed", 0)
            failed = result.get("failed", 0)
            if compliant:
                return (
                    f"Patient {pid} is compliant with all {len(rules_checked)} applicable protocol TG-101 rules. "
                    f"Rules checked: {', '.join(rules_checked)}. No violations found."
                )
            lines = [
                f"Patient {pid} has {len(issues)} protocol violation(s) across {failed} rule(s) "
                f"(checked {len(rules_checked)} rules, passed {passed}):\n"
            ]
            for issue in issues:
                lines.append(
                    f"• Rule {issue.get('rule', '?')} [{issue.get('severity', '?')}]: {issue.get('finding', '')}"
                )
            return "\n".join(lines)

        elif tool_name == "get_site_risk_history":
            history = result.get("history", [])
            sid = result.get("site_id", site_id)
            if not history:
                return f"No risk history data found for Site {sid}."
            lines = [f"Site {sid} risk history ({len(history)} periods):\n"]
            for h in history:
                lines.append(f"  {h.get('period', '?')}: Risk score {h.get('risk_score', '?')}/100 "
                             f"(deviations: {h.get('deviation_count', '?')}, major: {h.get('major_count', '?')})")
            if len(history) >= 2:
                first = history[0]["risk_score"]
                last = history[-1]["risk_score"]
                delta = last - first
                arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
                lines.append(f"\nOverall change: {arrow} {abs(delta)} points over {len(history)} periods.")
            return "\n".join(lines)

        elif tool_name == "analyze_deviation_pattern":
            sid = result.get("site_id", site_id)
            patterns = result.get("patterns", [])
            recurring = result.get("recurring_types", [])
            most = result.get("most_concerning")
            if not patterns:
                return f"No deviation pattern data found for Site {sid}."
            lines = [f"Deviation pattern analysis for Site {sid}:\n"]
            for p in patterns[:6]:
                status = "⚠ RECURRING" if p.get("is_recurring") else "ISOLATED"
                lines.append(
                    f"  • {p['deviation_type'].replace('_', ' ').title()}: {p['occurrences']} occurrences, "
                    f"{p['unique_patient_count']} patient(s) — {status}"
                )
            if recurring:
                lines.append(f"\nRecurring deviation types: {', '.join(t.replace('_', ' ').title() for t in recurring)}")
            if most:
                lines.append(f"Most concerning: {most.replace('_', ' ').title()}")
            return "\n".join(lines)

        elif tool_name == "get_affected_patients":
            sid = result.get("site_id", site_id)
            dev_type = result.get("deviation_type", "?")
            count = result.get("affected_patient_count", 0)
            dev_count = result.get("deviation_count", 0)
            patients = result.get("patients", [])
            if not patients:
                return f"No patients affected by {dev_type.replace('_', ' ').title()} deviations at Site {sid}."
            lines = [
                f"Site {sid} — {dev_type.replace('_', ' ').title()} deviations:\n"
                f"{dev_count} deviation(s) affecting {count} patient(s).\n"
            ]
            for p in patients[:10]:
                lines.append(f"  • {p['patient_id']} (age {p.get('age', '?')}, {p.get('status', '?')})")
            return "\n".join(lines)

        return "I have retrieved the requested information from the trial database."


# ─── Real MCP Bob Provider ────────────────────────────────────────────────────

class MCPBobProvider:
    """
    REAL IBM BOB PROVIDER — replaces LocalDemoBobProvider for the web UI.

    Routes /api/bob/ask directly through the MCP server tool layer.
    No keyword routing — tools are called based on explicit intent detection,
    identical to how IBM Bob selects tools, but running in-process.

    Architecture:
        Browser → POST /api/bob/ask → server.py
            → MCPBobProvider.answer()
            → build_bob_tools(repo, sess)   ← same boundary
            → TrialGuard tool
            → MongoDB
    """
    name = "TrialGuard Demo Assistant"

    # Intent → tool mapping (same rules as the MCP tool descriptions)
    # Uses the same _INTENT_RULES + _classify_intent logic from LocalDemoBobProvider
    # by delegating to it — we inherit the intent layer, keep each provider's own name.

    def __init__(self, repo: Any, sess: dict):
        self._repo = repo
        self._sess = sess
        self._tools = build_bob_tools(repo, sess)
        # Reuse LocalDemoBobProvider's intent classifier; do NOT overwrite its name
        self._delegate = LocalDemoBobProvider()

    def answer(self, question: str, user: User, tools: dict[str, Callable]) -> dict:
        """
        Call the underlying TrialGuard tools directly via the same path
        that the MCP server uses. Returns the same response structure
        the frontend expects.
        """
        # Rebuild tools scoped to this user's session (RBAC enforced)
        scoped_sess = {
            "role": user.role,
            "user_id": user.user_id,
            "site_id": user.site_id,
        }
        scoped_tools = build_bob_tools(self._repo, scoped_sess)

        # Delegate to LocalDemoBobProvider's answer() which has the full intent
        # classification, RBAC downgrade, site-scope guard, and _compose_answer.
        result = self._delegate.answer(question, user, scoped_tools)
        return result
