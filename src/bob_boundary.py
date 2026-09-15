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
            rules = [r for r in rules if q in r.get("name", "").lower() or q in r.get("domain", "").lower()]
        return {"protocol_id": protocol.get("protocol_id"), "rules": rules, "sources": ["Protocol repository"]}

    def compare_patient_to_protocol(patient_id: str, **_) -> dict:
        _check_role(TOOL_REGISTRY["compare_patient_to_protocol"]["roles"])
        patient = repo.find_one("patients", "patient_id", patient_id)
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")
        _check_site_scope(patient["site_id"])
        issues = []
        age = patient.get("age", 30)
        if not (18 <= age <= 65):
            issues.append({"rule": "R-001", "finding": f"Age {age} outside 18–65 window", "severity": "MAJOR"})
        return {
            "patient_id": patient_id,
            "site_id": patient["site_id"],
            "issues": issues,
            "compliant": len(issues) == 0,
            "sources": ["Patient repository", "Protocol TG-101"],
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
    }


# ─── Bob provider boundary ────────────────────────────────────────────────────

class LocalDemoBobProvider:
    """
    LOCAL DEMO ADAPTER — NOT IBM BOB.

    This adapter provides deterministic, evidence-backed natural-language responses
    by calling the same MCP-ready tool contracts that a real IBM Bob integration would use.

    To connect to IBM Bob: implement IBMBobProvider with the same .answer() interface.
    """
    name = "DEMO BOB ADAPTER (not IBM Bob)"

    # Quick prompt patterns → tool routing (order matters: more specific first)
    _ROUTES = [
        (["explain", "why", "reason", "driver", "what makes"], "explain_site_risk"),
        (["recommend", "what should we do", "what to do", "actions", "what can we"], "recommend_site_actions"),
        (["trend", "trajectory", "isolated", "pattern", "getting worse", "worsening"], "get_site_trends"),
        (["capa", "corrective action", "preventive action"], "generate_capa"),
        (["major deviation", "serious deviation"], "list_site_deviations"),
        (["highest risk", "high risk", "most at risk", "riskiest", "which sites"], "list_high_risk_sites"),
        (["summary", "overview", "summarize", "total", "how many"], "get_trial_overview"),
        (["report"], "generate_risk_report"),
    ]

    def answer(self, question: str, user: User, tools: dict[str, Callable]) -> dict:
        lowered = question.lower()

        # Permission check: site coordinator cross-site access
        if user.role == "SITE_COORDINATOR":
            import re
            sites_mentioned = re.findall(r'\bS\d{3}\b', question)
            for mentioned in sites_mentioned:
                if mentioned != user.site_id:
                    return {
                        "answer": (
                            f"You do not have permission to access Site {mentioned}'s information. "
                            f"Your access is restricted to Site {user.site_id}."
                        ),
                        "sources": [],
                        "provider": self.name,
                        "tool_result": None,
                    }

        # Determine target site
        import re
        site_matches = re.findall(r'\bS\d{3}\b', question)
        target_site = site_matches[0] if site_matches else (user.site_id or "S037")

        # Route to tool
        tool_name = "explain_site_risk"
        for keywords, name in self._ROUTES:
            if any(kw in lowered for kw in keywords):
                tool_name = name
                break

        # Role-based tool downgrade: if the selected tool isn't allowed for this role, fall back
        if tool_name in ("generate_capa", "recommend_site_actions") and user.role == "AUDITOR":
            tool_name = "explain_site_risk"
        if tool_name in ("list_high_risk_sites", "get_trial_overview") and user.role == "SITE_COORDINATOR":
            # Coordinator can't query all sites — show their own site instead
            tool_name = "explain_site_risk"
        if tool_name in ("generate_capa", "recommend_site_actions") and user.role == "SITE_COORDINATOR":
            # Coordinator can't generate CAPAs — show their site risk instead
            tool_name = "explain_site_risk"

        try:
            fn = tools.get(tool_name)
            if not fn:
                return {"answer": "That tool is not available.", "sources": [], "provider": self.name, "tool_result": None}

            # Call tool with appropriate params
            if tool_name in ("explain_site_risk", "get_site_risk", "recommend_site_actions",
                             "list_site_deviations", "get_site_trends", "generate_risk_report"):
                result = fn(site_id=target_site)
            elif tool_name == "generate_capa":
                result = fn(site_id=target_site)
            elif tool_name == "list_high_risk_sites":
                result = fn()
            elif tool_name == "get_trial_overview":
                result = fn()
            else:
                result = fn(site_id=target_site)

            answer = self._compose_answer(tool_name, result, target_site, question, user)
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
            return {"answer": str(e), "sources": [], "provider": self.name, "tool_result": None}
        except Exception as e:
            return {"answer": f"Unable to process that request: {e}", "sources": [], "provider": self.name, "tool_result": None}

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
                f"Root Cause (AI hypothesis — requires qualified review): {result.get('root_cause', '')}\n\n"
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

        return "I have retrieved the requested information from the trial database."
