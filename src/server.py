"""
TrialGuard AI — HTTP Server
Python standard-library HTTP server exposing a REST JSON API.
"""
from __future__ import annotations
import json
import os
import re
import secrets
import traceback
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from config import settings
from database import create_repository
from models import ROLES, RepositoryState
from security import hash_password, verify_password
from synthetic_data import build_demo_state
from engines import classify_severity, calculate_site_risk, run_deviation_engine
from bob_boundary import LocalDemoBobProvider, tool_contracts, build_bob_tools


# ─── session store ────────────────────────────────────────────────────────────
_sessions: dict[str, dict] = {}


def _new_session(user: dict) -> str:
    token = secrets.token_hex(32)
    _sessions[token] = {
        "user_id": user["user_id"],
        "email": user["email"],
        "role": user["role"],
        "site_id": user.get("site_id"),
        "name": user["name"],
    }
    return token


def _get_session(token: str) -> dict | None:
    return _sessions.get(token)


def _delete_session(token: str) -> None:
    _sessions.pop(token, None)


# ─── repository singleton ──────────────────────────────────────────────────────
_repo = create_repository()
if not _repo.all("users"):
    print("No data found - seeding demo data automatically...")
    _repo.replace_all(build_demo_state())
    print("Demo data seeded.")

_bob_provider = LocalDemoBobProvider()


# ─── helpers ──────────────────────────────────────────────────────────────────
def _json(obj: Any) -> bytes:
    return json.dumps(obj, default=str).encode()


def _error(code: int, message: str) -> tuple[int, bytes]:
    return code, _json({"error": message, "status": code})


def _audit(user_id: str, action: str, resource_type: str, resource_id: str = "", metadata: dict | None = None) -> None:
    import uuid
    _repo.insert("audit_events", {
        "event_id": str(uuid.uuid4()),
        "user_id": user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
    })


def _parse_cookie(header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in header.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies[k] = v
    return cookies


def _authorize(session: dict | None, allowed_roles: list[str] | None = None) -> tuple[dict | None, tuple[int, bytes] | None]:
    if session is None:
        return None, _error(401, "Authentication required")
    if allowed_roles and session["role"] not in allowed_roles:
        return None, _error(403, "Insufficient permissions")
    return session, None


def _site_scope(session: dict, site_id: str) -> bool:
    """Returns True if user is permitted to access site_id."""
    if session["role"] in ("STUDY_MANAGER", "SYSTEM_ADMIN", "AUDITOR"):
        return True
    if session["role"] == "SITE_COORDINATOR":
        return session.get("site_id") == site_id
    return False


# ─── handler ──────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  # suppress default stdout noise
        pass

    def _session(self) -> dict | None:
        cookie_header = self.headers.get("Cookie", "")
        token = _parse_cookie(cookie_header).get("tg_session")
        if not token:
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth[7:]
        return _get_session(token) if token else None

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _send(self, code: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, obj: Any) -> None:
        self._send(code, _json(obj))

    def _send_error(self, code: int, message: str) -> None:
        self._send_json(code, {"error": message, "status": code})

    # ── routing ───────────────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
        self.end_headers()

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PATCH(self):
        self._route("PATCH")

    def _route(self, method: str) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            # Static files
            if method == "GET" and not path.startswith("/api"):
                self._serve_static(path)
                return

            # API routes
            sess = self._session()

            # Auth endpoints (no session required)
            if path == "/api/auth/login" and method == "POST":
                self._login()
                return
            if path == "/api/auth/logout" and method == "POST":
                self._logout(sess)
                return

            # All other API routes require authentication
            if sess is None:
                self._send_error(401, "Authentication required")
                return

            # Dashboard
            if path == "/api/dashboard/summary" and method == "GET":
                self._dashboard_summary(sess)
            elif path == "/api/dashboard/charts" and method == "GET":
                self._dashboard_charts(sess)

            # Protocol
            elif path == "/api/protocol" and method == "GET":
                self._get_protocol(sess)
            elif path == "/api/protocol/analyze" and method == "POST":
                self._analyze_protocol(sess)

            # Sites
            elif path == "/api/sites" and method == "GET":
                self._list_sites(sess)
            elif re.match(r"^/api/sites/[^/]+$", path) and method == "GET":
                site_id = path.split("/")[-1]
                self._get_site(sess, site_id)
            elif re.match(r"^/api/sites/[^/]+/risk$", path) and method == "GET":
                site_id = path.split("/")[-2]
                self._get_site_risk(sess, site_id)
            elif re.match(r"^/api/sites/[^/]+/deviations$", path) and method == "GET":
                site_id = path.split("/")[-2]
                self._get_site_deviations(sess, site_id)
            elif re.match(r"^/api/sites/[^/]+/trends$", path) and method == "GET":
                site_id = path.split("/")[-2]
                self._get_site_trends(sess, site_id)
            elif re.match(r"^/api/sites/[^/]+/patients$", path) and method == "GET":
                site_id = path.split("/")[-2]
                self._get_site_patients(sess, site_id)

            # Deviations
            elif path == "/api/deviations" and method == "GET":
                self._list_deviations(sess, qs)
            elif path == "/api/deviations/analyze" and method == "POST":
                self._analyze_deviations(sess)
            elif re.match(r"^/api/deviations/[^/]+$", path) and method == "GET":
                dev_id = path.split("/")[-1]
                self._get_deviation(sess, dev_id)

            # CAPA
            elif path == "/api/capa" and method == "GET":
                self._list_capa(sess)
            elif path == "/api/capa/generate" and method == "POST":
                self._generate_capa(sess)
            elif re.match(r"^/api/capa/[^/]+$", path) and method == "GET":
                capa_id = path.split("/")[-1]
                self._get_capa(sess, capa_id)
            elif re.match(r"^/api/capa/[^/]+$", path) and method == "PATCH":
                capa_id = path.split("/")[-1]
                self._update_capa(sess, capa_id)

            # Reports
            elif re.match(r"^/api/reports/site/[^/]+$", path) and method == "GET":
                site_id = path.split("/")[-1]
                self._site_report(sess, site_id)
            elif path == "/api/reports/trial" and method == "GET":
                self._trial_report(sess)
            elif path == "/api/reports/deviations" and method == "GET":
                self._deviations_report(sess)
            elif path == "/api/reports/capa" and method == "GET":
                self._capa_report(sess)

            # Audit
            elif path == "/api/audit" and method == "GET":
                self._list_audit(sess)

            # Bob
            elif path == "/api/bob/tools" and method == "GET":
                self._send_json(200, tool_contracts())
            elif path == "/api/bob/tool" and method == "POST":
                self._bob_tool(sess)
            elif path == "/api/bob/ask" and method == "POST":
                self._bob_ask(sess)

            # Users (admin)
            elif path == "/api/users" and method == "GET":
                self._list_users(sess)

            # Risk recalc
            elif path == "/api/risk/recalculate" and method == "POST":
                self._recalculate_risk(sess)

            else:
                self._send_error(404, f"Endpoint not found: {method} {path}")

        except Exception:
            tb = traceback.format_exc()
            print(f"[ERROR] {method} {path}\n{tb}")
            self._send_error(500, "Internal server error")

    # ── static file serving ───────────────────────────────────────────────────

    def _serve_static(self, path: str) -> None:
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        if path == "/" or path == "":
            file_path = os.path.join(static_dir, "index.html")
        elif path.startswith("/static/"):
            rel = path[len("/static/"):]
            file_path = os.path.join(static_dir, rel)
        else:
            file_path = os.path.join(static_dir, "index.html")

        if not os.path.exists(file_path):
            self._send_error(404, "File not found")
            return

        ext = os.path.splitext(file_path)[1]
        mime = {".html": "text/html", ".css": "text/css", ".js": "application/javascript",
                ".json": "application/json", ".png": "image/png", ".ico": "image/x-icon"}.get(ext, "application/octet-stream")
        with open(file_path, "rb") as f:
            data = f.read()
        self._send(200, data, mime)

    # ── auth ──────────────────────────────────────────────────────────────────

    def _login(self) -> None:
        body = self._body()
        email = (body.get("email") or "").strip().lower()
        password = body.get("password") or ""
        if not email or not password:
            self._send_error(400, "Email and password required")
            return
        user = _repo.find_one("users", "email", email)
        if not user or not verify_password(password, user["password_hash"]):
            self._send_error(401, "Invalid credentials")
            return
        token = _new_session(user)
        _audit(user["user_id"], "LOGIN", "session", user["user_id"])
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Set-Cookie", f"tg_session={token}; HttpOnly; Path=/; SameSite=Strict")
        self.send_header("Access-Control-Allow-Origin", "*")
        body_bytes = _json({"token": token, "user": {k: v for k, v in user.items() if k != "password_hash"}})
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _logout(self, sess: dict | None) -> None:
        cookie_header = self.headers.get("Cookie", "")
        token = _parse_cookie(cookie_header).get("tg_session")
        if token:
            _delete_session(token)
        if sess:
            _audit(sess["user_id"], "LOGOUT", "session", sess["user_id"])
        self._send_json(200, {"status": "logged_out"})

    # ── dashboard ─────────────────────────────────────────────────────────────

    def _dashboard_summary(self, sess: dict) -> None:
        _audit(sess["user_id"], "VIEW_DASHBOARD", "dashboard")
        sites = _repo.all("sites")
        patients = _repo.all("patients")
        deviations = _repo.all("deviations")
        risk_scores = _repo.all("risk_scores")
        capa_records = _repo.all("capa_records")

        if sess["role"] == "SITE_COORDINATOR":
            sid = sess["site_id"]
            patients = [p for p in patients if p["site_id"] == sid]
            deviations = [d for d in deviations if d["site_id"] == sid]
            risk_scores = [r for r in risk_scores if r["site_id"] == sid]
            capa_records = [c for c in capa_records if c["site_id"] == sid]

        high_risk = [r for r in risk_scores if r["risk_level"] == "HIGH"]
        self._send_json(200, {
            "total_sites": len(sites) if sess["role"] != "SITE_COORDINATOR" else 1,
            "total_patients": len(patients),
            "total_deviations": len(deviations),
            "major_deviations": sum(1 for d in deviations if d["severity"] == "MAJOR"),
            "minor_deviations": sum(1 for d in deviations if d["severity"] == "MINOR"),
            "admin_deviations": sum(1 for d in deviations if d["severity"] == "ADMINISTRATIVE"),
            "high_risk_sites": len(high_risk),
            "open_capas": sum(1 for c in capa_records if c["status"] in ("OPEN", "IN_PROGRESS")),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        })

    def _dashboard_charts(self, sess: dict) -> None:
        deviations = _repo.all("deviations")
        risk_scores = _repo.all("risk_scores")
        capa_records = _repo.all("capa_records")

        if sess["role"] == "SITE_COORDINATOR":
            sid = sess["site_id"]
            deviations = [d for d in deviations if d["site_id"] == sid]
            risk_scores = [r for r in risk_scores if r["site_id"] == sid]

        risk_dist = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for r in risk_scores:
            risk_dist[r.get("risk_level", "LOW")] += 1

        from collections import Counter
        dev_by_type = Counter(d["type"] for d in deviations)
        dev_by_severity = Counter(d["severity"] for d in deviations)
        # Deviation trend by detected_at date (group by week)
        trend: dict[str, dict[str, int]] = {}
        for d in deviations:
            date_str = d.get("detected_at", "2026-05-01")[:7]  # YYYY-MM
            if date_str not in trend:
                trend[date_str] = {"MAJOR": 0, "MINOR": 0, "ADMINISTRATIVE": 0}
            trend[date_str][d["severity"]] += 1
        sorted_trend = [{"period": k, **v} for k, v in sorted(trend.items())]

        capa_status = Counter(c["status"] for c in capa_records)

        # Top 10 high-risk sites
        high_risk_sites = sorted(
            [r for r in risk_scores if r.get("risk_level") == "HIGH"],
            key=lambda x: x["current_score"], reverse=True
        )[:10]
        for r in high_risk_sites:
            site = _repo.find_one("sites", "site_id", r["site_id"])
            r["site_name"] = site["name"] if site else r["site_id"]

        self._send_json(200, {
            "risk_distribution": risk_dist,
            "deviation_trend": sorted_trend,
            "deviation_by_type": dict(dev_by_type),
            "deviation_by_severity": dict(dev_by_severity),
            "capa_status": dict(capa_status),
            "high_risk_sites": high_risk_sites,
        })

    # ── protocol ──────────────────────────────────────────────────────────────

    def _get_protocol(self, sess: dict) -> None:
        protocols = _repo.all("protocols")
        _audit(sess["user_id"], "VIEW_PROTOCOL", "protocol")
        self._send_json(200, protocols[0] if protocols else {})

    def _analyze_protocol(self, sess: dict) -> None:
        if sess["role"] not in ("STUDY_MANAGER", "SYSTEM_ADMIN"):
            self._send_error(403, "Not permitted")
            return
        deviations = _repo.all("deviations")
        protocols = _repo.all("protocols")
        protocol = protocols[0] if protocols else {}
        from collections import Counter
        rule_violations = Counter(
            d["evidence"].get("rule_id", "unknown") for d in deviations if d.get("evidence")
        )
        domains = {}
        for rule in protocol.get("rules", []):
            domain = rule["domain"]
            domains[domain] = domains.get(domain, 0) + rule_violations.get(rule["rule_id"], 0)
        self._send_json(200, {
            "protocol": protocol,
            "compliance_by_domain": [
                {"domain": k, "violations": v, "compliance_pct": max(0, round(100 - (v / max(len(deviations), 1)) * 100, 1))}
                for k, v in domains.items()
            ],
            "total_violations": len(deviations),
        })

    # ── sites ─────────────────────────────────────────────────────────────────

    def _list_sites(self, sess: dict) -> None:
        sites = _repo.all("sites")
        risk_scores = {r["site_id"]: r for r in _repo.all("risk_scores")}
        if sess["role"] == "SITE_COORDINATOR":
            sites = [s for s in sites if s["site_id"] == sess["site_id"]]
        result = []
        for s in sites:
            r = risk_scores.get(s["site_id"], {})
            result.append({**s, "risk_score": r.get("current_score", 0), "risk_level": r.get("risk_level", "LOW"), "trend": r.get("trend", "STABLE")})
        _audit(sess["user_id"], "VIEW_SITES", "sites")
        self._send_json(200, sorted(result, key=lambda x: -x["risk_score"]))

    def _get_site(self, sess: dict, site_id: str) -> None:
        if not _site_scope(sess, site_id):
            self._send_error(403, "Access to this site is not permitted")
            return
        site = _repo.find_one("sites", "site_id", site_id)
        if not site:
            self._send_error(404, "Site not found")
            return
        _audit(sess["user_id"], "VIEW_SITE", "site", site_id)
        risk = _repo.find_one("risk_scores", "site_id", site_id) or {}
        patients = _repo.find_many("patients", "site_id", site_id)
        deviations = _repo.find_many("deviations", "site_id", site_id)
        self._send_json(200, {**site, "risk": risk, "patient_count": len(patients), "deviation_count": len(deviations)})

    def _get_site_risk(self, sess: dict, site_id: str) -> None:
        if not _site_scope(sess, site_id):
            self._send_error(403, "Access to this site is not permitted")
            return
        risk = _repo.find_one("risk_scores", "site_id", site_id)
        if not risk:
            self._send_error(404, "Risk data not found")
            return
        _audit(sess["user_id"], "VIEW_SITE_RISK", "risk_score", site_id)
        self._send_json(200, risk)

    def _get_site_deviations(self, sess: dict, site_id: str) -> None:
        if not _site_scope(sess, site_id):
            self._send_error(403, "Access to this site is not permitted")
            return
        devs = _repo.find_many("deviations", "site_id", site_id)
        _audit(sess["user_id"], "VIEW_SITE_DEVIATIONS", "deviations", site_id)
        self._send_json(200, devs)

    def _get_site_trends(self, sess: dict, site_id: str) -> None:
        if not _site_scope(sess, site_id):
            self._send_error(403, "Access to this site is not permitted")
            return
        risk = _repo.find_one("risk_scores", "site_id", site_id) or {}
        devs = _repo.find_many("deviations", "site_id", site_id)
        from collections import Counter
        dev_types = Counter(d["type"] for d in devs)
        _audit(sess["user_id"], "VIEW_SITE_TRENDS", "trends", site_id)
        self._send_json(200, {
            "site_id": site_id,
            "current_score": risk.get("current_score", 0),
            "predicted_score": risk.get("predicted_score", 0),
            "trend": risk.get("trend", "STABLE"),
            "sparkline": risk.get("sparkline", []),
            "deviation_counts_by_type": dict(dev_types),
            "leading_indicators": risk.get("leading_indicators", []),
            "risk_drivers": risk.get("risk_drivers", []),
            "prediction_window": risk.get("prediction_window", "next monitoring period"),
        })

    def _get_site_patients(self, sess: dict, site_id: str) -> None:
        if not _site_scope(sess, site_id):
            self._send_error(403, "Access to this site is not permitted")
            return
        patients = _repo.find_many("patients", "site_id", site_id)
        _audit(sess["user_id"], "VIEW_SITE_PATIENTS", "patients", site_id)
        self._send_json(200, patients)

    # ── deviations ────────────────────────────────────────────────────────────

    def _list_deviations(self, sess: dict, qs: dict) -> None:
        devs = _repo.all("deviations")
        if sess["role"] == "SITE_COORDINATOR":
            devs = [d for d in devs if d["site_id"] == sess["site_id"]]
        severity = (qs.get("severity") or [None])[0]
        site_filter = (qs.get("site_id") or [None])[0]
        status_filter = (qs.get("status") or [None])[0]
        if severity:
            devs = [d for d in devs if d["severity"] == severity.upper()]
        if site_filter:
            if not _site_scope(sess, site_filter):
                self._send_error(403, "Access not permitted")
                return
            devs = [d for d in devs if d["site_id"] == site_filter]
        if status_filter:
            devs = [d for d in devs if d["status"] == status_filter.upper()]
        _audit(sess["user_id"], "VIEW_DEVIATIONS", "deviations")
        self._send_json(200, devs)

    def _get_deviation(self, sess: dict, dev_id: str) -> None:
        dev = _repo.find_one("deviations", "deviation_id", dev_id)
        if not dev:
            self._send_error(404, "Deviation not found")
            return
        if not _site_scope(sess, dev["site_id"]):
            self._send_error(403, "Access not permitted")
            return
        _audit(sess["user_id"], "VIEW_DEVIATION", "deviation", dev_id)
        self._send_json(200, dev)

    def _analyze_deviations(self, sess: dict) -> None:
        if sess["role"] not in ("STUDY_MANAGER", "SYSTEM_ADMIN"):
            self._send_error(403, "Not permitted")
            return
        protocols = _repo.all("protocols")
        patients = _repo.all("patients")
        visits = _repo.all("visits")
        medications = _repo.all("medications")
        new_devs = run_deviation_engine(protocols, patients, visits, medications)
        _audit(sess["user_id"], "ANALYZE_DEVIATIONS", "deviations", "", {"new_count": len(new_devs)})
        self._send_json(200, {"analyzed": len(new_devs), "deviations": new_devs[:20]})

    # ── capa ──────────────────────────────────────────────────────────────────

    def _list_capa(self, sess: dict) -> None:
        records = _repo.all("capa_records")
        if sess["role"] == "SITE_COORDINATOR":
            records = [c for c in records if c["site_id"] == sess["site_id"]]
        _audit(sess["user_id"], "VIEW_CAPA", "capa_records")
        self._send_json(200, records)

    def _generate_capa(self, sess: dict) -> None:
        if sess["role"] not in ("STUDY_MANAGER", "SYSTEM_ADMIN"):
            self._send_error(403, "Only Study Managers and Admins may generate CAPA")
            return
        body = self._body()
        site_id = body.get("site_id")
        if not site_id:
            self._send_error(400, "site_id required")
            return
        site = _repo.find_one("sites", "site_id", site_id)
        if not site:
            self._send_error(404, "Site not found")
            return
        devs = _repo.find_many("deviations", "site_id", site_id)
        deviation_ids = body.get("deviation_ids") or [d["deviation_id"] for d in devs if d["severity"] == "MAJOR"][:5]
        selected_devs = [d for d in devs if d["deviation_id"] in deviation_ids]

        import uuid
        from collections import Counter
        from services import generate_capa_record
        record = generate_capa_record(site_id, selected_devs, sess["user_id"])
        _repo.insert("capa_records", record)
        _audit(sess["user_id"], "GENERATE_CAPA", "capa_records", record["capa_id"],
               {"site_id": site_id, "deviation_count": len(deviation_ids)})
        self._send_json(201, record)

    def _get_capa(self, sess: dict, capa_id: str) -> None:
        record = _repo.find_one("capa_records", "capa_id", capa_id)
        if not record:
            self._send_error(404, "CAPA not found")
            return
        if sess["role"] == "SITE_COORDINATOR" and record["site_id"] != sess["site_id"]:
            self._send_error(403, "Access not permitted")
            return
        _audit(sess["user_id"], "VIEW_CAPA", "capa_records", capa_id)
        self._send_json(200, record)

    def _update_capa(self, sess: dict, capa_id: str) -> None:
        if sess["role"] in ("AUDITOR",):
            self._send_error(403, "Auditors cannot modify CAPA records")
            return
        record = _repo.find_one("capa_records", "capa_id", capa_id)
        if not record:
            self._send_error(404, "CAPA not found")
            return
        if sess["role"] == "SITE_COORDINATOR" and record["site_id"] != sess["site_id"]:
            self._send_error(403, "Access not permitted")
            return
        body = self._body()
        allowed = {"status", "corrective_actions", "preventive_actions", "priority", "owner"}
        changes = {k: v for k, v in body.items() if k in allowed}
        changes["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated = _repo.update("capa_records", "capa_id", capa_id, changes)
        _audit(sess["user_id"], "UPDATE_CAPA", "capa_records", capa_id, {"changes": list(changes.keys())})
        self._send_json(200, updated)

    # ── reports ───────────────────────────────────────────────────────────────

    def _site_report(self, sess: dict, site_id: str) -> None:
        if not _site_scope(sess, site_id):
            self._send_error(403, "Access not permitted")
            return
        site = _repo.find_one("sites", "site_id", site_id)
        risk = _repo.find_one("risk_scores", "site_id", site_id) or {}
        devs = _repo.find_many("deviations", "site_id", site_id)
        capas = [c for c in _repo.all("capa_records") if c["site_id"] == site_id]
        _audit(sess["user_id"], "GENERATE_REPORT", "report", site_id, {"report_type": "site_risk"})
        self._send_json(200, {
            "report_type": "site_risk",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": sess["name"],
            "site": site,
            "risk": risk,
            "deviations": devs,
            "capa_records": capas,
            "disclaimer": "This report is generated from synthetic data for demonstration purposes. Not for clinical or regulatory use.",
        })

    def _trial_report(self, sess: dict) -> None:
        if sess["role"] not in ("STUDY_MANAGER", "AUDITOR", "SYSTEM_ADMIN"):
            self._send_error(403, "Not permitted")
            return
        sites = _repo.all("sites")
        risk_scores = _repo.all("risk_scores")
        devs = _repo.all("deviations")
        capas = _repo.all("capa_records")
        _audit(sess["user_id"], "GENERATE_REPORT", "report", "all", {"report_type": "trial_summary"})
        self._send_json(200, {
            "report_type": "trial_summary",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": sess["name"],
            "total_sites": len(sites),
            "high_risk_sites": [r for r in risk_scores if r.get("risk_level") == "HIGH"],
            "total_deviations": len(devs),
            "major_deviations": sum(1 for d in devs if d["severity"] == "MAJOR"),
            "open_capas": sum(1 for c in capas if c["status"] in ("OPEN", "IN_PROGRESS")),
            "disclaimer": "Synthetic data. Not for clinical or regulatory use.",
        })

    def _deviations_report(self, sess: dict) -> None:
        devs = _repo.all("deviations")
        if sess["role"] == "SITE_COORDINATOR":
            devs = [d for d in devs if d["site_id"] == sess["site_id"]]
        _audit(sess["user_id"], "GENERATE_REPORT", "report", "deviations", {"report_type": "deviations"})
        self._send_json(200, {
            "report_type": "deviations",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "deviations": devs,
            "disclaimer": "Synthetic data. Not for clinical or regulatory use.",
        })

    def _capa_report(self, sess: dict) -> None:
        capas = _repo.all("capa_records")
        if sess["role"] == "SITE_COORDINATOR":
            capas = [c for c in capas if c["site_id"] == sess["site_id"]]
        _audit(sess["user_id"], "GENERATE_REPORT", "report", "capa", {"report_type": "capa"})
        self._send_json(200, {
            "report_type": "capa",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "capa_records": capas,
            "disclaimer": "Synthetic data. Not for clinical or regulatory use.",
        })

    # ── audit ─────────────────────────────────────────────────────────────────

    def _list_audit(self, sess: dict) -> None:
        if sess["role"] not in ("STUDY_MANAGER", "AUDITOR", "SYSTEM_ADMIN"):
            self._send_error(403, "Not permitted")
            return
        events = _repo.all("audit_events")
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        self._send_json(200, events[:500])

    # ── users ─────────────────────────────────────────────────────────────────

    def _list_users(self, sess: dict) -> None:
        if sess["role"] != "SYSTEM_ADMIN":
            self._send_error(403, "Admin only")
            return
        users = _repo.all("users")
        safe = [{k: v for k, v in u.items() if k != "password_hash"} for u in users]
        self._send_json(200, safe)

    # ── risk recalculate ──────────────────────────────────────────────────────

    def _recalculate_risk(self, sess: dict) -> None:
        if sess["role"] not in ("STUDY_MANAGER", "SYSTEM_ADMIN"):
            self._send_error(403, "Not permitted")
            return
        sites = _repo.all("sites")
        deviations = _repo.all("deviations")
        for site in sites:
            existing = _repo.find_one("risk_scores", "site_id", site["site_id"])
            prev = existing["current_score"] if existing else 0
            new_risk = calculate_site_risk(site["site_id"], deviations, prev)
            new_risk["calculated_at"] = datetime.now(timezone.utc).isoformat()
            if existing:
                _repo.update("risk_scores", "site_id", site["site_id"], new_risk)
            else:
                _repo.insert("risk_scores", new_risk)
        _audit(sess["user_id"], "RISK_RECALCULATED", "risk_scores", "all")
        self._send_json(200, {"status": "recalculated", "sites": len(sites)})

    # ── bob ───────────────────────────────────────────────────────────────────

    def _bob_tool(self, sess: dict) -> None:
        body = self._body()
        tool_name = body.get("tool_name")
        params = body.get("params", {})
        if not tool_name:
            self._send_error(400, "tool_name required")
            return
        tools = build_bob_tools(_repo, sess)
        fn = tools.get(tool_name)
        if not fn:
            self._send_error(404, f"Tool '{tool_name}' not found")
            return
        try:
            result = fn(**params)
        except PermissionError as e:
            self._send_error(403, str(e))
            return
        except TypeError as e:
            self._send_error(400, f"Invalid parameters: {e}")
            return
        _audit(sess["user_id"], "BOB_TOOL_CALLED", "bob", tool_name, {"params": params})
        self._send_json(200, result)

    def _bob_ask(self, sess: dict) -> None:
        body = self._body()
        question = body.get("question", "").strip()
        if not question:
            self._send_error(400, "question required")
            return
        tools = build_bob_tools(_repo, sess)
        from models import User
        user_obj = User(
            user_id=sess["user_id"],
            name=sess["name"],
            email=sess["email"],
            password_hash="",
            role=sess["role"],
            site_id=sess.get("site_id"),
        )
        result = _bob_provider.answer(question, user_obj, tools)
        _audit(sess["user_id"], "BOB_QUESTION", "bob", "", {"question": question[:200]})
        self._send_json(200, result)


# ─── entry point ──────────────────────────────────────────────────────────────

def run_server() -> None:
    server = HTTPServer((settings.host, settings.port), Handler)
    sep = "=" * 60
    print(f"\n{sep}")
    print("  TrialGuard AI - Clinical Trial Risk Monitor")
    print(sep)
    print(f"  URL:      http://{settings.host}:{settings.port}")
    print(f"  Backend:  {_repo.backend}")
    print(f"  Data:     {len(_repo.all('sites'))} sites, {len(_repo.all('patients'))} patients")
    print("\n  Demo accounts (password: TrialGuard2026!)")
    print("  manager@trialguard.demo   -> STUDY_MANAGER")
    print("  site037@trialguard.demo   -> SITE_COORDINATOR (S037)")
    print("  auditor@trialguard.demo   -> AUDITOR")
    print("  admin@trialguard.demo     -> SYSTEM_ADMIN")
    print(f"{sep}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    run_server()
