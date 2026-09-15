from __future__ import annotations

import json
import secrets
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bob_boundary import LocalDemoBobProvider, build_bob_tools, tool_contracts
from config import settings
from database import create_repository
from engines import calculate_site_risk, classify_severity
from models import User
from security import verify_password
from synthetic_data import build_demo_state

ROOT = Path(__file__).parent
REPOSITORY = create_repository()
STATE = build_demo_state()
try:
    REPOSITORY.replace_all(STATE)
except Exception as error:
    print(f"Seed persistence unavailable; continuing with local state ({error.__class__.__name__}).")
SESSIONS: dict[str, User] = {}
BOB = LocalDemoBobProvider()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def user_from_record(record: dict | None) -> User | None:
    if not record:
        return None
    return User(record["user_id"], record["name"], record["email"], record["password_hash"], record["role"], record.get("site_id"))


def public_user(user: User | None) -> dict | None:
    if not user:
        return None
    return {"user_id": user.user_id, "name": user.name, "email": user.email, "role": user.role, "site_id": user.site_id}


def current_user(handler: BaseHTTPRequestHandler) -> User | None:
    authorization = handler.headers.get("Authorization", "")
    token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else handler.headers.get("Cookie", "").replace("trialguard_session=", "").split(";", 1)[0].strip()
    return SESSIONS.get(token)


def json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    try:
        return json.loads(handler.rfile.read(length) or b"{}")
    except (json.JSONDecodeError, ValueError):
        return {}


def send_json(handler, payload, status=200, headers=None):
    body = json.dumps(payload, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    if headers:
        for key, value in headers.items():
            handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(body)


def fail(handler, status, message):
    send_json(handler, {"error": message, "status": status}, status)


def audit(user: User | None, action: str, resource_type: str, resource_id: str, metadata=None):
    REPOSITORY.insert("audit_events", {"event_id": secrets.token_hex(8), "user_id": user.user_id if user else "anonymous", "action": action, "resource_type": resource_type, "resource_id": resource_id, "timestamp": now(), "metadata": metadata or {}})


def authorized_site(user: User, site_id: str | None) -> bool:
    return user.role != "SITE_COORDINATOR" or user.site_id == site_id


def scoped(items: list[dict], user: User, field="site_id") -> list[dict]:
    if user.role == "SITE_COORDINATOR":
        return [item for item in items if item.get(field) == user.site_id]
    return items


def visible_site(user: User, site_id: str) -> dict | None:
    if not authorized_site(user, site_id):
        return None
    return REPOSITORY.find_one("sites", "site_id", site_id)


def site_payload(user: User, site_id: str) -> dict | None:
    site = visible_site(user, site_id)
    if not site:
        return None
    risk = REPOSITORY.find_one("risk_scores", "site_id", site_id) or calculate_site_risk(site_id, REPOSITORY.all("deviations"))
    deviations = REPOSITORY.find_many("deviations", "site_id", site_id)
    patients = REPOSITORY.find_many("patients", "site_id", site_id)
    severity = {key: sum(item["severity"] == key for item in deviations) for key in ("MAJOR", "MINOR", "ADMINISTRATIVE")}
    return {**site, "risk": risk, "patients": len(patients), "deviations": len(deviations), "severity_distribution": severity, "protocol_compliance": max(0, 100 - min(95, len(deviations) // 2)), "trend_history": [max(0, risk["previous_score"] - 8), risk["previous_score"], risk["current_score"], risk["predicted_score"]]}


def bob_tools(user: User) -> dict:
    def overview(actor):
        sites = scoped(REPOSITORY.all("sites"), actor)
        deviations = scoped(REPOSITORY.all("deviations"), actor)
        return {"sites": len(sites), "patients": len(scoped(REPOSITORY.all("patients"), actor)), "deviations": len(deviations), "high_risk_sites": sum(item["risk_level"] == "HIGH" for item in scoped(REPOSITORY.all("risk_scores"), actor))}

    def high_risk(actor):
        risks = sorted(scoped(REPOSITORY.all("risk_scores"), actor), key=lambda item: item["current_score"], reverse=True)
        return {"sites": risks[:10], "sources": ["risk_scores", "deviations"]}

    def site_risk(actor, site_id):
        if not authorized_site(actor, site_id):
            raise PermissionError
        return REPOSITORY.find_one("risk_scores", "site_id", site_id) or {}

    def explain(actor, site_id):
        result = site_risk(actor, site_id)
        result["sources"] = ["risk_scores", "deviations", "protocols"]
        return result

    def site_deviations(actor, site_id):
        if not authorized_site(actor, site_id):
            raise PermissionError
        return {"deviations": REPOSITORY.find_many("deviations", "site_id", site_id), "sources": ["deviations"]}

    def get_deviation(actor, deviation_id):
        deviation = REPOSITORY.find_one("deviations", "deviation_id", deviation_id)
        if not deviation or not authorized_site(actor, deviation.get("site_id")):
            raise PermissionError
        return {"deviation": deviation, "sources": ["deviations", "protocols"]}

    def search_protocol_rules(actor, query=""):
        rules = REPOSITORY.all("protocols")[0]["rules"]
        return {"rules": [rule for rule in rules if not query or query.lower() in json.dumps(rule).lower()], "sources": ["protocols"]}

    def compare_patient(actor, patient_id):
        patient = REPOSITORY.find_one("patients", "patient_id", patient_id)
        if not patient or not authorized_site(actor, patient.get("site_id")):
            raise PermissionError
        findings = [item for item in REPOSITORY.find_many("deviations", "patient_id", patient_id)]
        return {"patient_id": patient_id, "compliant": not findings, "findings": findings, "sources": ["patients", "visits", "deviations"]}

    def trends(actor, site_id):
        if not authorized_site(actor, site_id):
            raise PermissionError
        risk = site_risk(actor, site_id)
        return {"site_id": site_id, "history": [max(0, risk["previous_score"] - 8), risk["previous_score"], risk["current_score"], risk["predicted_score"]], "sources": ["risk_scores", "deviations"]}

    def actions(actor, site_id):
        if not authorized_site(actor, site_id):
            raise PermissionError
        return {"site_id": site_id, "actions": ["Review affected records", "Verify affected patients", "Conduct targeted site staff training", "Increase monitoring frequency"], "requires_qualified_review": True, "sources": ["risk_scores", "deviations"]}

    def generate_capa(actor, site_id):
        if actor.role not in {"STUDY_MANAGER", "SYSTEM_ADMIN"}:
            raise PermissionError
        deviations = REPOSITORY.find_many("deviations", "site_id", site_id)[:3]
        capa = {"capa_id": f"CAPA-{len(REPOSITORY.all('capa_records')) + 1:04d}", "site_id": site_id, "deviation_ids": [item["deviation_id"] for item in deviations], "problem_statement": f"Recurring protocol deviations at {site_id}", "root_cause": "AI-generated hypothesis: process variation requires qualified review", "corrective_actions": ["Review affected records", "Verify affected patients", "Conduct targeted staff training"], "preventive_actions": ["Add secondary verification", "Increase monitoring frequency"], "priority": "HIGH", "status": "OPEN", "created_by": actor.user_id, "created_at": now(), "updated_at": now()}
        REPOSITORY.insert("capa_records", capa)
        audit(actor, "CAPA_GENERATED", "capa", capa["capa_id"], {"site_id": site_id})
        return capa

    def capa_status(actor, capa_id):
        capa = REPOSITORY.find_one("capa_records", "capa_id", capa_id)
        if not capa or not authorized_site(actor, capa.get("site_id")):
            raise PermissionError
        return capa

    def report(actor, site_id=None):
        if site_id and not authorized_site(actor, site_id):
            raise PermissionError
        return {"title": "TrialGuard Risk Report", "site_id": site_id, "summary": overview(actor), "generated_at": now(), "sources": ["risk_scores", "deviations", "capa_records"]}

    return {"get_trial_overview": overview, "list_high_risk_sites": high_risk, "get_site_risk": site_risk, "explain_site_risk": explain, "list_site_deviations": site_deviations, "get_deviation": get_deviation, "search_protocol_rules": search_protocol_rules, "compare_patient_to_protocol": compare_patient, "get_site_trends": trends, "recommend_site_actions": actions, "generate_capa": generate_capa, "get_capa_status": capa_status, "generate_risk_report": report}


class TrialGuardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path.startswith("/static/"):
            relative = "static/index.html" if path == "/" else path.removeprefix("/")
            content_type = "text/html" if relative.endswith(".html") else ("text/css" if relative.endswith(".css") else "application/javascript")
            return self.serve_file(ROOT / relative, content_type)
        user = current_user(self)
        if path == "/api/auth/me":
            return send_json(self, {"authenticated": bool(user), "user": public_user(user)})
        if not user:
            return fail(self, 401, "Authentication required")
        try:
            return self.handle_get(path, user)
        except PermissionError:
            return fail(self, 403, "You do not have permission to access this resource")
        except Exception as error:
            print(f"GET {path}: {error}")
            return fail(self, 500, "Unable to process request")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/auth/login":
            body = json_body(self)
            record = REPOSITORY.find_one("users", "email", str(body.get("email", "")).lower())
            if not record or not verify_password(str(body.get("password", "")), record["password_hash"]):
                return fail(self, 401, "Invalid demo credentials")
            user = user_from_record(record)
            token = secrets.token_urlsafe(32)
            SESSIONS[token] = user
            audit(user, "LOGIN", "session", token[:8])
            return send_json(self, {"user": public_user(user), "backend": REPOSITORY.backend, "session_token": token}, headers={"Set-Cookie": f"trialguard_session={token}; HttpOnly; SameSite=Lax; Max-Age={settings.session_hours * 3600}"})
        user = current_user(self)
        if not user:
            return fail(self, 401, "Authentication required")
        try:
            return self.handle_post(path, user, json_body(self))
        except PermissionError:
            return fail(self, 403, "Your role cannot perform this action")
        except Exception as error:
            print(f"POST {path}: {error}")
            return fail(self, 500, "Unable to process request")

    def do_PATCH(self):
        user = current_user(self)
        if not user:
            return fail(self, 401, "Authentication required")
        if user.role not in {"STUDY_MANAGER", "SYSTEM_ADMIN"}:
            return fail(self, 403, "Only managers and administrators can update CAPA records")
        path = urlparse(self.path).path
        capa_id = path.rsplit("/", 1)[-1]
        updated = REPOSITORY.update("capa_records", "capa_id", capa_id, {"status": json_body(self).get("status", "IN_PROGRESS"), "updated_at": now()})
        if not updated:
            return fail(self, 404, "CAPA not found")
        audit(user, "CAPA_UPDATED", "capa", capa_id)
        return send_json(self, updated)

    def handle_get(self, path: str, user: User):
        if path == "/api/dashboard/summary":
            sites = scoped(REPOSITORY.all("sites"), user)
            deviations = scoped(REPOSITORY.all("deviations"), user)
            risks = scoped(REPOSITORY.all("risk_scores"), user)
            capas = scoped(REPOSITORY.all("capa_records"), user)
            return send_json(self, {"total_sites": len(sites), "total_patients": len(scoped(REPOSITORY.all("patients"), user)), "total_deviations": len(deviations), "major_deviations": sum(item["severity"] == "MAJOR" for item in deviations), "minor_deviations": sum(item["severity"] == "MINOR" for item in deviations), "administrative_deviations": sum(item["severity"] == "ADMINISTRATIVE" for item in deviations), "high_risk_sites": sum(item["risk_level"] == "HIGH" for item in risks), "open_capas": sum(item["status"] != "COMPLETED" for item in capas), "risk_distribution": {level: sum(item["risk_level"] == level for item in risks) for level in ("HIGH", "MEDIUM", "LOW")}, "deviation_types": {key: sum(item["type"] == key for item in deviations) for key in sorted({item["type"] for item in deviations})}, "high_risk": sorted([site_payload(user, item["site_id"]) for item in risks if item["risk_level"] == "HIGH"], key=lambda item: item["risk"]["current_score"], reverse=True)[:8], "recent_deviations": sorted(deviations, key=lambda item: item["detected_at"], reverse=True)[:10], "backend": REPOSITORY.backend})
        if path == "/api/sites":
            return send_json(self, [site_payload(user, item["site_id"]) for item in scoped(REPOSITORY.all("sites"), user)])
        if path.startswith("/api/sites/"):
            site_id = path.split("/")[3]
            payload = site_payload(user, site_id)
            if not payload:
                return fail(self, 404 if visible_site(user, site_id) else 403, "Site not found or outside your assigned scope")
            audit(user, "SITE_VIEWED", "site", site_id)
            if path.endswith("/risk"):
                return send_json(self, payload["risk"])
            if path.endswith("/deviations"):
                return send_json(self, scoped(REPOSITORY.find_many("deviations", "site_id", site_id), user))
            if path.endswith("/trends"):
                return send_json(self, {"site_id": site_id, "history": payload["trend_history"], "current": payload["risk"]["current_score"], "projected": payload["risk"]["predicted_score"]})
            return send_json(self, payload)
        if path == "/api/deviations":
            return send_json(self, scoped(REPOSITORY.all("deviations"), user))
        if path.startswith("/api/deviations/"):
            deviation_id = path.rsplit("/", 1)[-1]
            deviation = REPOSITORY.find_one("deviations", "deviation_id", deviation_id)
            if not deviation or not authorized_site(user, deviation.get("site_id")):
                return fail(self, 404 if deviation is None else 403, "Deviation not found or outside your assigned scope")
            return send_json(self, deviation)
        if path == "/api/protocol":
            return send_json(self, REPOSITORY.all("protocols")[0])
        if path == "/api/reports/site/S037":
            site = site_payload(user, "S037")
            return send_json(self, {"title": "TrialGuard Site Risk Report", "generated_at": now(), "site": site, "synthetic": True})
        if path == "/api/capa":
            return send_json(self, scoped(REPOSITORY.all("capa_records"), user))
        if path.startswith("/api/capa/"):
            capa = REPOSITORY.find_one("capa_records", "capa_id", path.rsplit("/", 1)[-1])
            if not capa or not authorized_site(user, capa.get("site_id")):
                return fail(self, 404 if not capa else 403, "CAPA not found or outside your assigned scope")
            return send_json(self, capa)
        if path == "/api/audit":
            if user.role not in {"STUDY_MANAGER", "AUDITOR", "SYSTEM_ADMIN"}:
                return fail(self, 403, "Audit trail is restricted")
            return send_json(self, REPOSITORY.all("audit_events")[-100:][::-1])
        if path == "/api/bob/tools":
            return send_json(self, {"provider": BOB.name, "tools": tool_contracts()})
        if path == "/api/reports/trial":
            return send_json(self, {"title": "TrialGuard AI Trial Summary", "generated_at": now(), "summary": self.handle_get_summary(user)})
        return fail(self, 404, "Route not found")

    def handle_get_summary(self, user):
        sites = scoped(REPOSITORY.all("sites"), user)
        risks = scoped(REPOSITORY.all("risk_scores"), user)
        return {"sites": len(sites), "high_risk_sites": sum(item["risk_level"] == "HIGH" for item in risks), "synthetic": True}

    def handle_post(self, path: str, user: User, body: dict):
        if path == "/api/auth/logout":
            token = self.headers.get("Cookie", "").replace("trialguard_session=", "").split(";", 1)[0]
            SESSIONS.pop(token, None)
            audit(user, "LOGOUT", "session", token[:8])
            return send_json(self, {"ok": True}, headers={"Set-Cookie": "trialguard_session=; HttpOnly; Max-Age=0"})
        if path == "/api/bob/tool":
            tool_name = body.get("tool_name")
            if tool_name not in bob_tools(user):
                return fail(self, 400, "Unknown or unavailable tool")
            site_id = body.get("site_id", user.site_id or "S037")
            tool = bob_tools(user)[tool_name]
            if tool_name in {"get_site_risk", "explain_site_risk", "list_site_deviations", "get_site_trends", "recommend_site_actions", "generate_capa", "generate_risk_report"}:
                result = tool(user, site_id)
            elif tool_name == "get_deviation":
                result = tool(user, body.get("deviation_id", "DEV-0001"))
            elif tool_name == "compare_patient_to_protocol":
                result = tool(user, body.get("patient_id", "P-037-001"))
            elif tool_name == "search_protocol_rules":
                result = tool(user, body.get("query", ""))
            elif tool_name == "get_capa_status":
                result = tool(user, body.get("capa_id", "CAPA-0001"))
            else:
                result = tool(user)
            audit(user, "BOB_TOOL_CALLED", "bob_tool", tool_name, {"site_id": site_id})
            return send_json(self, {"tool_name": tool_name, "result": result, "provider": BOB.name})
        if path == "/api/bob/ask":
            question = str(body.get("question", ""))
            session = {"user_id": user.user_id, "email": user.email, "role": user.role, "site_id": user.site_id, "name": user.name}
            result = BOB.answer(question, user, build_bob_tools(REPOSITORY, session))
            audit(user, "BOB_TOOL_CALLED", "bob_question", "trial", {"question": question[:120]})
            return send_json(self, result)
        if path == "/api/capa/generate":
            if user.role not in {"STUDY_MANAGER", "SYSTEM_ADMIN"}:
                raise PermissionError
            site_id = body.get("site_id", user.site_id)
            if not site_id or not authorized_site(user, site_id):
                raise PermissionError
            result = bob_tools(user)["generate_capa"](user, site_id)
            return send_json(self, result, 201)
        if path == "/api/risk/recalculate":
            if user.role not in {"STUDY_MANAGER", "SYSTEM_ADMIN"}:
                raise PermissionError
            state = build_demo_state()
            REPOSITORY.replace_all(state)
            audit(user, "RISK_RECALCULATED", "trial", "TG-101")
            return send_json(self, {"ok": True, "sites": len(state.sites), "deviations": len(state.deviations)})
        if path == "/api/deviations/analyze":
            factors = body.get("factors", {"safety": 3, "integrity": 3, "criticality": 2, "rights": 0, "magnitude": 1, "recurrence": 0})
            return send_json(self, classify_severity(factors))
        if path == "/api/protocol/analyze":
            return send_json(self, {"protocol_id": "TG-101", "rules_verified": len(REPOSITORY.all("protocols")[0]["rules"]), "deviations_detected": len(scoped(REPOSITORY.all("deviations"), user)), "method": "deterministic comparison", "synthetic": True})
        return fail(self, 404, "Route not found")

    def serve_file(self, path: Path, content_type: str):
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            return fail(self, 404, "File not found")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    print(f"TrialGuard AI: http://{settings.host}:{settings.port} ({REPOSITORY.backend} backend)")
    ThreadingHTTPServer((settings.host, settings.port), TrialGuardHandler).serve_forever()
