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
from socketserver import ThreadingMixIn
from typing import Any

from config import settings
from database import create_repository
from models import ROLES, RepositoryState
from security import hash_password, verify_password
from synthetic_data import build_demo_state
from engines import classify_severity, calculate_site_risk, run_deviation_engine, evaluate_blacklist, SITE_BLACKLIST_RISK_THRESHOLD
from bob_boundary import MCPBobProvider, tool_contracts, build_bob_tools


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

_bob_provider = MCPBobProvider(_repo, {"role": "STUDY_MANAGER", "user_id": "server", "site_id": None})


# ─── helpers ──────────────────────────────────────────────────────────────────
def _json(obj: Any) -> bytes:
    return json.dumps(obj, default=str, ensure_ascii=False).encode("utf-8")


def _error(code: int, message: str) -> tuple[int, bytes]:
    return code, _json({"error": message, "status": code})


def _audit(user_id: str, action: str, resource_type: str, resource_id: str = "", metadata: dict | None = None) -> None:
    import uuid
    import threading
    def _write():
        _repo.insert("audit_events", {
            "event_id": str(uuid.uuid4()),
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        })
    threading.Thread(target=_write, daemon=True).start()


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

    def _send(self, code: int, body: bytes, content_type: str = "application/json; charset=utf-8") -> None:
        try:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass  # client disconnected before we finished — not a server error

    def _send_json(self, code: int, obj: Any) -> None:
        self._send(code, _json(obj), "application/json; charset=utf-8")

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

            # Medicines / Trials
            if path == "/api/medicines" and method == "GET":
                self._list_medicines(sess)
            elif path == "/api/trials" and method == "GET":
                self._list_trials(sess, qs)

            # Dashboard
            elif path == "/api/dashboard/summary" and method == "GET":
                self._dashboard_summary(sess, qs)
            elif path == "/api/dashboard/charts" and method == "GET":
                self._dashboard_charts(sess, qs)
            elif path == "/api/dashboard/attention" and method == "GET":
                self._dashboard_attention(sess, qs)
            elif path == "/api/dashboard/heatmap" and method == "GET":
                self._dashboard_heatmap(sess, qs)
            elif path == "/api/dashboard/emerging-sites" and method == "GET":
                self._dashboard_emerging_sites(sess, qs)

            # Protocol
            elif path == "/api/protocol" and method == "GET":
                self._get_protocol(sess)
            elif path == "/api/protocol/analyze" and method == "POST":
                self._analyze_protocol(sess)

            # Sites
            elif path == "/api/sites" and method == "GET":
                self._list_sites(sess, qs)
            elif path == "/api/sites/blacklisted" and method == "GET":
                self._list_blacklisted_sites(sess)
            elif re.match(r"^/api/sites/[^/]+/blacklist$", path) and method == "POST":
                site_id = path.split("/")[-2]
                self._blacklist_site(sess, site_id)
            elif re.match(r"^/api/sites/[^/]+/clear-blacklist$", path) and method == "POST":
                site_id = path.split("/")[-2]
                self._clear_blacklist(sess, site_id)
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
            elif re.match(r"^/api/sites/[^/]+/risk-history$", path) and method == "GET":
                site_id = path.split("/")[-2]
                self._get_site_risk_history(sess, site_id)
            elif re.match(r"^/api/sites/[^/]+/investigation$", path) and method == "GET":
                site_id = path.split("/")[-2]
                self._get_site_investigation(sess, site_id)
            elif re.match(r"^/api/sites/[^/]+/pattern$", path) and method in ("GET", "POST"):
                site_id = path.split("/")[-2]
                self._get_site_pattern(sess, site_id)

            # Deviations
            elif path == "/api/deviations" and method == "GET":
                self._list_deviations(sess, qs)  # qs already forwarded
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

            # Search
            elif path == "/api/search" and method == "GET":
                self._search(sess, qs)

            # Notifications
            elif path == "/api/notifications" and method == "GET":
                self._notifications(sess)

            # Users (admin)
            elif path == "/api/users" and method == "GET":
                self._list_users(sess)

            # Risk recalc
            elif path == "/api/risk/recalculate" and method == "POST":
                self._recalculate_risk(sess)

            else:
                self._send_error(404, f"Endpoint not found: {method} {path}")

        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass  # client closed the connection mid-flight — ignore silently
        except Exception:
            tb = traceback.format_exc()
            print(f"[ERROR] {method} {path}\n{tb}")
            try:
                self._send_error(500, "Internal server error")
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                pass  # connection already gone, can't send error response

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
        mime = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
            ".ico": "image/x-icon",
        }.get(ext, "application/octet-stream")
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
        self.send_header("Content-Type", "application/json; charset=utf-8")
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

    # ── medicines & trials ────────────────────────────────────────────────────

    def _list_medicines(self, sess: dict) -> None:
        medicines = _repo.all("medicines")
        self._send_json(200, medicines)

    def _list_trials(self, sess: dict, qs: dict) -> None:
        trials = _repo.all("trials")
        medicine_id = (qs.get("medicine_id") or [None])[0]
        if medicine_id:
            trials = [t for t in trials if t.get("medicine_id") == medicine_id]
        self._send_json(200, trials)

    # ── dashboard ─────────────────────────────────────────────────────────────

    def _dashboard_summary(self, sess: dict, qs: dict) -> None:
        trial_id = (qs.get("trial_id") or [None])[0]
        _audit(sess["user_id"], "VIEW_DASHBOARD", "dashboard")
        sites = _repo.all("sites")
        patients = _repo.all("patients")
        deviations = _repo.all("deviations")
        risk_scores = _repo.all("risk_scores")
        capa_records = _repo.all("capa_records")

        if trial_id:
            sites = [s for s in sites if s.get("trial_id") == trial_id]
            patients = [p for p in patients if p.get("trial_id") == trial_id]
            deviations = [d for d in deviations if d.get("trial_id") == trial_id]
            risk_scores = [r for r in risk_scores if r.get("trial_id") == trial_id]
            capa_records = [c for c in capa_records if c.get("trial_id") == trial_id]

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

    def _dashboard_charts(self, sess: dict, qs: dict) -> None:
        trial_id = (qs.get("trial_id") or [None])[0]
        deviations = _repo.all("deviations")
        risk_scores = _repo.all("risk_scores")
        capa_records = _repo.all("capa_records")

        if trial_id:
            deviations = [d for d in deviations if d.get("trial_id") == trial_id]
            risk_scores = [r for r in risk_scores if r.get("trial_id") == trial_id]
            capa_records = [c for c in capa_records if c.get("trial_id") == trial_id]

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


    def _dashboard_attention(self, sess: dict, qs: dict) -> None:
        trial_id = (qs.get("trial_id") or [None])[0]
        _audit(sess["user_id"], "VIEW_DASHBOARD_ATTENTION", "dashboard")
        risk_scores = _repo.all("risk_scores")
        deviations = _repo.all("deviations")

        if trial_id:
            risk_scores = [r for r in risk_scores if r.get("trial_id") == trial_id]
            deviations = [d for d in deviations if d.get("trial_id") == trial_id]

        if sess["role"] == "SITE_COORDINATOR":
            sid = sess["site_id"]
            risk_scores = [r for r in risk_scores if r["site_id"] == sid]
            deviations = [d for d in deviations if d["site_id"] == sid]

        high_risk = [r for r in risk_scores if r.get("risk_level") == "HIGH"]
        high_risk_sorted = sorted(high_risk, key=lambda x: x.get("current_score", 0), reverse=True)

        attention_sites = []
        for r in high_risk_sorted[:3]:
            site = _repo.find_one("sites", "site_id", r["site_id"])
            attention_sites.append({
                "site_id": r["site_id"],
                "site_name": site["name"] if site else r["site_id"],
                "current_score": r.get("current_score", 0),
                "predicted_score": r.get("predicted_score", r.get("current_score", 0)),
                "trend": r.get("trend", "STABLE"),
                "leading_indicators": r.get("leading_indicators", []),
            })

        worsening = [r for r in risk_scores if r.get("trend") == "WORSENING"]
        worsening_sorted = sorted(worsening, key=lambda x: x.get("current_score", 0), reverse=True)
        from collections import Counter
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        all_history = _repo.all("risk_history")
        early_warnings = []
        for r in worsening_sorted[:3]:
            sid = r["site_id"]
            site_devs = [d for d in deviations if d["site_id"] == sid]
            type_counts = dict(Counter(d["type"] for d in site_devs))

            # Dominant deviation type → human-readable primary signal
            if type_counts:
                dominant_type = max(type_counts, key=type_counts.get)
                type_label = dominant_type.replace("_", " ").title()
                dom_count = type_counts[dominant_type]
                # Check recurrence (>2 occurrences)
                if dom_count > 2:
                    primary_signal = f"Recurring {type_label.lower()} deviations ({dom_count})"
                else:
                    primary_signal = f"{type_label} ({dom_count})"
            else:
                primary_signal = "Elevated deviation frequency"

            # Recent deviation count (last 30 days of data — use max date as reference)
            all_dates = [d.get("detected_at") or "" for d in site_devs if d.get("detected_at")]
            if all_dates:
                max_date_str = max(all_dates)
                try:
                    max_date = _dt.strptime(max_date_str[:10], "%Y-%m-%d").date()
                    cutoff = max_date - _td(days=30)
                    recent_deviation_count = sum(
                        1 for d in site_devs
                        if d.get("detected_at") and d["detected_at"][:10] >= cutoff.isoformat()
                    )
                except (ValueError, TypeError):
                    recent_deviation_count = len(site_devs)
            else:
                recent_deviation_count = len(site_devs)

            # Risk change: current - previous score from history
            site_history = sorted(
                [h for h in all_history if h.get("site_id") == sid],
                key=lambda h: h.get("period", "")
            )
            if len(site_history) >= 2:
                risk_change = site_history[-1]["risk_score"] - site_history[-2]["risk_score"]
            else:
                risk_change = 0

            early_warnings.append({
                "site_id": sid,
                "current_score": r.get("current_score", 0),
                "predicted_score": r.get("predicted_score", r.get("current_score", 0)),
                "deviation_type_breakdown": type_counts,
                "primary_signal": primary_signal,
                "recent_deviation_count": recent_deviation_count,
                "risk_change": risk_change,
                "leading_indicators": r.get("leading_indicators", []),
            })

        if high_risk:
            avg_high = sum(r.get("current_score", 0) for r in high_risk) / len(high_risk)
            health_score = max(0, min(100, int(100 - (avg_high * 0.7 + len(high_risk) * 3))))
        else:
            health_score = 100

        if health_score < 40:
            health_level = "CRITICAL"
        elif health_score < 65:
            health_level = "CONCERNING"
        else:
            health_level = "STABLE"

        self._send_json(200, {
            "attention_sites": attention_sites,
            "early_warnings": early_warnings,
            "trial_health_score": health_score,
            "health_level": health_level,
        })

    def _dashboard_heatmap(self, sess: dict, qs: dict) -> None:
        trial_id = (qs.get("trial_id") or [None])[0]
        _audit(sess["user_id"], "VIEW_DASHBOARD_HEATMAP", "dashboard")
        sites = _repo.all("sites")
        risk_scores = _repo.all("risk_scores")

        if trial_id:
            sites = [s for s in sites if s.get("trial_id") == trial_id]
            risk_scores = [r for r in risk_scores if r.get("trial_id") == trial_id]

        risk_by_site = {r["site_id"]: r for r in risk_scores}

        result = []
        for s in sites:
            if sess["role"] == "SITE_COORDINATOR" and s["site_id"] != sess.get("site_id"):
                continue
            r = risk_by_site.get(s["site_id"], {})
            result.append({
                "site_id": s["site_id"],
                "name": s.get("name", s["site_id"]),
                "location": s.get("location", ""),
                "risk_score": r.get("current_score", 0),
                "risk_level": r.get("risk_level", "LOW"),
                "trend": r.get("trend", "STABLE"),
            })

        result.sort(key=lambda x: x["risk_score"], reverse=True)
        self._send_json(200, result)

    def _dashboard_emerging_sites(self, sess: dict, qs: dict) -> None:
        trial_id = (qs.get("trial_id") or [None])[0]
        _audit(sess["user_id"], "VIEW_DASHBOARD_EMERGING", "dashboard")
        all_history = _repo.all("risk_history")
        risk_scores = _repo.all("risk_scores")

        if trial_id:
            all_history = [h for h in all_history if h.get("trial_id") == trial_id]
            risk_scores = [r for r in risk_scores if r.get("trial_id") == trial_id]

        risk_by_site = {r["site_id"]: r for r in risk_scores}
        sites = _repo.all("sites")
        site_map = {s["site_id"]: s for s in sites}

        from collections import Counter

        # Pre-group deviations by site once — never call find_many in a loop
        all_devs = _repo.all("deviations")
        devs_by_site: dict[str, list] = {}
        for d in all_devs:
            devs_by_site.setdefault(d.get("site_id", ""), []).append(d)

        # Pre-group history by site
        site_history_map: dict[str, list] = {}
        for h in all_history:
            sid = h.get("site_id")
            if sid:
                site_history_map.setdefault(sid, []).append(h)

        emerging = []
        for sid, hist in site_history_map.items():
            if sess["role"] == "SITE_COORDINATOR" and sess.get("site_id") != sid:
                continue
            sorted_hist = sorted(hist, key=lambda h: h.get("period", ""))
            if len(sorted_hist) < 2:
                continue
            previous_score = sorted_hist[-2]["risk_score"]
            current_score = sorted_hist[-1]["risk_score"]
            change = current_score - previous_score
            if change <= 0:
                continue  # only worsening sites

            r = risk_by_site.get(sid, {})
            s = site_map.get(sid, {})

            # Primary signal — use pre-grouped deviations
            site_devs = devs_by_site.get(sid, [])
            if site_devs:
                type_counts = Counter(d["type"] for d in site_devs)
                dominant_type = max(type_counts, key=type_counts.get)
                dom_count = type_counts[dominant_type]
                if dom_count > 2:
                    primary_signal = f"Recurring {dominant_type.replace('_', ' ').lower()} deviations"
                else:
                    primary_signal = dominant_type.replace("_", " ").title()
            else:
                primary_signal = "Elevated deviation frequency"

            emerging.append({
                "site_id": sid,
                "site_name": s.get("name", sid),
                "previous_score": previous_score,
                "current_score": current_score,
                "risk_change": change,
                "projected_score": r.get("predicted_score", current_score + change),
                "trend": r.get("trend", "WORSENING"),
                "risk_level": r.get("risk_level", "MEDIUM"),
                "primary_signal": primary_signal,
            })

        emerging.sort(key=lambda x: -x["risk_change"])
        self._send_json(200, {"emerging_sites": emerging[:5]})


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

        # Proper denominators per domain
        patients = _repo.all("patients")
        visits = _repo.all("visits")
        total_patients = max(len(patients), 1)
        total_visits = max(len(visits), 1)
        # Expected visits = patients × 5 visits (for missed visit calc)
        expected_visits = max(total_patients * 5, 1)
        # Visit 2 and 3 are the windowed ones
        windowed_visits = max(sum(1 for v in visits if v.get("visit_number") in (2, 3)), 1)

        domain_denominators = {
            "Eligibility": total_patients,
            "Visit Schedule": windowed_visits,
            "Dosing": total_visits,
            "Concomitant Medications": total_patients,
            "Assessments": total_visits,
            "Data Integrity": total_visits,
        }

        rule_violations = Counter(
            d["evidence"].get("rule_id", "unknown") for d in deviations if d.get("evidence")
        )
        # Missed visits use expected_visits denominator
        missed_violations = rule_violations.get("R-008", 0)

        domains: dict[str, int] = {}
        for rule in protocol.get("rules", []):
            domain = rule["domain"]
            domains[domain] = domains.get(domain, 0) + rule_violations.get(rule["rule_id"], 0)

        compliance_by_domain = []
        for k, v in domains.items():
            if k == "Visit Schedule":
                # R-008 missed visits use expected_visits denominator
                missed = rule_violations.get("R-008", 0)
                windowed = v - missed
                denom = windowed_visits + expected_visits
                total_v = windowed + missed
            else:
                denom = domain_denominators.get(k, max(len(deviations), 1))
                total_v = v
            compliance_pct = max(0, round((1 - total_v / denom) * 100, 1))
            compliance_by_domain.append({"domain": k, "violations": v, "denominator": denom, "compliance_pct": compliance_pct})

        self._send_json(200, {
            "protocol": protocol,
            "compliance_by_domain": compliance_by_domain,
            "total_violations": len(deviations),
        })

    # ── sites ─────────────────────────────────────────────────────────────────

    def _list_sites(self, sess: dict, qs: dict) -> None:
        trial_id = (qs.get("trial_id") or [None])[0]
        sites = _repo.all("sites")
        if trial_id:
            sites = [s for s in sites if s.get("trial_id") == trial_id]
        risk_scores = {r["site_id"]: r for r in _repo.all("risk_scores")}
        if sess["role"] == "SITE_COORDINATOR":
            sites = [s for s in sites if s["site_id"] == sess["site_id"]]
        result = []
        for s in sites:
            r = risk_scores.get(s["site_id"], {})
            result.append({**s, "risk_score": r.get("current_score", 0), "risk_level": r.get("risk_level", "LOW"), "trend": r.get("trend", "STABLE")})
        _audit(sess["user_id"], "VIEW_SITES", "sites")
        self._send_json(200, sorted(result, key=lambda x: -x["risk_score"]))

    def _list_blacklisted_sites(self, sess: dict) -> None:
        allowed = ("STUDY_MANAGER", "SYSTEM_ADMIN", "AUDITOR")
        if sess["role"] not in allowed:
            self._send_error(403, "Not permitted")
            return
        sites = _repo.all("sites")
        risk_scores = {r["site_id"]: r for r in _repo.all("risk_scores")}
        blacklisted = [s for s in sites if s.get("is_blacklisted")]
        # STUDY_MANAGER with no site_id = global scope (authorized for all)
        if sess["role"] == "STUDY_MANAGER" and sess.get("site_id") is not None:
            # Scoped SM: only sites in their authorized trials
            coordinator_site = _repo.find_one("sites", "site_id", sess["site_id"])
            authorized_trial = coordinator_site["trial_id"] if coordinator_site else None
            blacklisted = [s for s in blacklisted if s.get("trial_id") == authorized_trial]
        result = [
            {
                "site_id": s["site_id"],
                "name": s["name"],
                "trial_id": s.get("trial_id"),
                "risk_score": risk_scores.get(s["site_id"], {}).get("current_score", 0),
                "is_blacklisted": s["is_blacklisted"],
                "blacklist_reason": s.get("blacklist_reason"),
                "blacklisted_at": s.get("blacklisted_at"),
                "blacklisted_by": s.get("blacklisted_by"),
                "blacklist_source": s.get("blacklist_source"),
            }
            for s in blacklisted
        ]
        result.sort(key=lambda x: -x["risk_score"])
        _audit(sess["user_id"], "VIEW_BLACKLISTED_SITES", "sites")
        self._send_json(200, result)

    def _blacklist_site(self, sess: dict, site_id: str) -> None:
        if sess["role"] not in ("STUDY_MANAGER", "SYSTEM_ADMIN"):
            self._send_error(403, "Only Study Managers and System Admins may blacklist sites")
            return
        site = _repo.find_one("sites", "site_id", site_id)
        if not site:
            self._send_error(404, "Site not found")
            return
        if site.get("is_blacklisted"):
            self._send_json(200, {"status": "already_blacklisted", "message": f"Site {site_id} is already blacklisted"})
            return
        body = self._body()
        reason = body.get("reason", "").strip()
        if not reason:
            self._send_error(400, "reason is required")
            return
        now = datetime.now(timezone.utc).isoformat()
        risk = _repo.find_one("risk_scores", "site_id", site_id) or {}
        risk_score = risk.get("current_score", 0)
        changes = {
            "is_blacklisted": True,
            "blacklist_reason": reason,
            "blacklisted_at": now,
            "blacklisted_by": sess["user_id"],
            "blacklist_source": sess["role"],
            "blacklist_cleared_by": None,
            "blacklist_cleared_at": None,
            "blacklist_clear_reason": None,
        }
        _repo.update("sites", "site_id", site_id, changes)
        _audit(sess["user_id"], "SITE_BLACKLISTED", "sites", site_id,
               metadata={"site_id": site_id, "reason": reason, "actor": sess["user_id"],
                         "role": sess["role"], "source": sess["role"], "risk_score": risk_score})
        self._send_json(200, {"status": "blacklisted", "site_id": site_id})

    def _clear_blacklist(self, sess: dict, site_id: str) -> None:
        if sess["role"] not in ("STUDY_MANAGER", "SYSTEM_ADMIN"):
            self._send_error(403, "Only Study Managers and System Admins may clear blacklists")
            return
        site = _repo.find_one("sites", "site_id", site_id)
        if not site:
            self._send_error(404, "Site not found")
            return
        if not site.get("is_blacklisted"):
            self._send_json(200, {"status": "not_blacklisted"})
            return
        body = self._body()
        reason = body.get("reason", "").strip()
        if not reason:
            self._send_error(400, "reason is required")
            return
        now = datetime.now(timezone.utc).isoformat()
        changes = {
            "is_blacklisted": False,
            "blacklist_cleared_by": sess["user_id"],
            "blacklist_cleared_at": now,
            "blacklist_clear_reason": reason,
        }
        _repo.update("sites", "site_id", site_id, changes)
        _audit(sess["user_id"], "SITE_BLACKLIST_CLEARED", "sites", site_id,
               metadata={"site_id": site_id, "cleared_by": sess["user_id"],
                         "cleared_by_role": sess["role"], "reason": reason, "cleared_at": now})
        self._send_json(200, {"status": "cleared", "site_id": site_id, "cleared_at": now})

    def _check_blacklist_guard(self, site_id: str, session: dict) -> tuple[int, dict] | None:
        """Return (403, error_dict) if site is blacklisted and session role is SITE_COORDINATOR, else None."""
        if session["role"] != "SITE_COORDINATOR":
            return None
        site = _repo.find_one("sites", "site_id", site_id)
        if site and site.get("is_blacklisted"):
            return (403, {
                "error": "SITE_BLACKLISTED",
                "message": (
                    f"Site {site_id} is currently blacklisted. Write actions are restricted "
                    "until the blacklist is cleared by a Study Manager or System Admin."
                ),
            })
        return None

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

    def _get_site_risk_history(self, sess: dict, site_id: str) -> None:
        if not _site_scope(sess, site_id):
            self._send_error(403, "Access to this site is not permitted")
            return
        if not _repo.find_one("sites", "site_id", site_id):
            self._send_error(404, "Site not found")
            return
        _audit(sess["user_id"], "VIEW_SITE_RISK_HISTORY", "risk_history", site_id)
        history = [h for h in _repo.all("risk_history") if h.get("site_id") == site_id]
        history.sort(key=lambda h: h.get("period", ""))
        self._send_json(200, {"site_id": site_id, "history": history})

    def _get_site_investigation(self, sess: dict, site_id: str) -> None:
        if not _site_scope(sess, site_id):
            self._send_error(403, "Access to this site is not permitted")
            return
        site = _repo.find_one("sites", "site_id", site_id)
        if not site:
            self._send_error(404, "Site not found")
            return
        _audit(sess["user_id"], "VIEW_SITE_INVESTIGATION", "investigation", site_id)

        risk = _repo.find_one("risk_scores", "site_id", site_id) or {}
        devs = _repo.find_many("deviations", "site_id", site_id)
        patients = _repo.find_many("patients", "site_id", site_id)
        capas = [c for c in _repo.all("capa_records") if c["site_id"] == site_id]
        history = sorted(
            [h for h in _repo.all("risk_history") if h.get("site_id") == site_id],
            key=lambda h: h.get("period", "")
        )

        from collections import Counter
        from services import analyze_deviation_pattern
        protocols = _repo.all("protocols")
        protocol = protocols[0] if protocols else {}
        rules_map = {r["rule_id"]: r for r in protocol.get("rules", [])}

        # Deviation summary
        sev_counts = Counter(d["severity"] for d in devs)
        type_counts = Counter(d["type"] for d in devs)
        by_type = dict(type_counts)

        # Top 5 most recent major deviations
        major_devs = sorted(
            [d for d in devs if d["severity"] == "MAJOR"],
            key=lambda d: d.get("detected_at", ""),
            reverse=True,
        )[:5]

        # Affected patients
        patient_dev_counts = Counter(d["patient_id"] for d in devs if d.get("patient_id"))
        affected_patients = [
            {"patient_id": pid, "deviation_count": cnt}
            for pid, cnt in patient_dev_counts.most_common(10)
        ]

        # Risk driver breakdown
        risk_drivers_raw = []
        major_count = sev_counts.get("MAJOR", 0)
        if major_count > 0:
            risk_drivers_raw.append({"factor": "Major deviations", "points": major_count * 3})
        dosing_errors = type_counts.get("INCORRECT_DOSE", 0)
        if dosing_errors > 0:
            risk_drivers_raw.append({"factor": "Dosing errors", "points": dosing_errors * 3})
        missed_visits = type_counts.get("MISSED_VISIT", 0)
        if missed_visits > 0:
            risk_drivers_raw.append({"factor": "Missed visits", "points": missed_visits * 2})
        data_delays = type_counts.get("LATE_DATA_ENTRY", 0)
        if data_delays > 0:
            risk_drivers_raw.append({"factor": "Data delays", "points": data_delays})
        prohibited = type_counts.get("PROHIBITED_MEDICATION", 0)
        if prohibited > 0:
            risk_drivers_raw.append({"factor": "Prohibited medications", "points": prohibited * 3})
        total_points = sum(r["points"] for r in risk_drivers_raw) or 1
        for r in risk_drivers_raw:
            r["pct"] = round(r["points"] / total_points * 100)

        # Recurrence / pattern analysis
        pattern_data = analyze_deviation_pattern(site_id, devs, patients)

        # Protocol rules violated
        rule_ids_violated = list({
            d["evidence"].get("rule_id")
            for d in devs
            if d.get("evidence") and d["evidence"].get("rule_id")
        })

        # CAPA
        capa_info = {"exists": False, "capa_id": None, "status": None}
        if capas:
            latest = sorted(capas, key=lambda c: c.get("created_at", ""), reverse=True)[0]
            capa_info = {"exists": True, "capa_id": latest["capa_id"], "status": latest["status"]}

        # Primary signal & recommendation
        most_concerning = pattern_data.get("most_concerning")
        if most_concerning:
            primary_signal = most_concerning.replace("_", " ").title() + " (recurring)" if most_concerning in pattern_data.get("recurring_types", []) else most_concerning.replace("_", " ").title()
        else:
            primary_signal = "Elevated protocol deviation frequency"

        risk_level = risk.get("risk_level", "MEDIUM")
        if risk_level == "HIGH":
            recommendation = "Immediate CAPA review recommended. Escalate to Study Manager."
        elif risk_level == "MEDIUM":
            recommendation = "Increased monitoring frequency recommended. Review deviation trends."
        else:
            recommendation = "Continue standard monitoring. No immediate intervention required."

        self._send_json(200, {
            "site_id": site_id,
            "site": site,
            "risk": {
                "current_score": risk.get("current_score", 0),
                "predicted_score": risk.get("predicted_score", 0),
                "risk_level": risk_level,
                "trend": risk.get("trend", "STABLE"),
                "leading_indicators": risk.get("leading_indicators", []),
                "risk_drivers": risk.get("risk_drivers", []),
            },
            "risk_history": history,
            "risk_driver_breakdown": risk_drivers_raw,
            "deviation_summary": {
                "total": len(devs),
                "major": sev_counts.get("MAJOR", 0),
                "minor": sev_counts.get("MINOR", 0),
                "admin": sev_counts.get("ADMINISTRATIVE", 0),
                "by_type": by_type,
            },
            "top_deviations": major_devs,
            "affected_patients": affected_patients,
            "recurrence": {
                "recurring_types": pattern_data.get("recurring_types", []),
                "isolated_types": pattern_data.get("isolated_types", []),
                "patterns": pattern_data.get("patterns", []),
            },
            "capa": capa_info,
            "protocol_rules_violated": rule_ids_violated,
            "primary_signal": primary_signal,
            "recommendation_summary": recommendation,
        })

    def _get_site_pattern(self, sess: dict, site_id: str) -> None:
        if not _site_scope(sess, site_id):
            self._send_error(403, "Access to this site is not permitted")
            return
        if not _repo.find_one("sites", "site_id", site_id):
            self._send_error(404, "Site not found")
            return
        _audit(sess["user_id"], "VIEW_SITE_PATTERN", "deviations", site_id)
        devs = _repo.find_many("deviations", "site_id", site_id)
        patients = _repo.find_many("patients", "site_id", site_id)
        from services import analyze_deviation_pattern
        result = analyze_deviation_pattern(site_id, devs, patients)
        self._send_json(200, result)

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

        # Enhance with evidence chain data
        site_id = dev["site_id"]
        dev_type = dev.get("type", "")
        rule_id = (dev.get("evidence") or {}).get("rule_id")

        # Protocol rule
        protocols = _repo.all("protocols")
        protocol = protocols[0] if protocols else {}
        rules = protocol.get("rules", [])
        protocol_rule = next((r for r in rules if r.get("rule_id") == rule_id), None)

        # Related deviations of same type at same site
        all_site_devs = _repo.find_many("deviations", "site_id", site_id)
        related = [
            {"deviation_id": d["deviation_id"], "patient_id": d.get("patient_id"), "detected_at": d.get("detected_at"), "severity": d.get("severity")}
            for d in all_site_devs
            if d["deviation_id"] != dev_id and d.get("type") == dev_type
        ][:5]

        # Affected patient count at site with same type
        affected_patient_count = len({d.get("patient_id") for d in all_site_devs if d.get("type") == dev_type and d.get("patient_id")})

        # Risk contribution estimate based on severity score
        sev_score = dev.get("severity_score", 0)
        risk_contribution = round(sev_score * 0.6)

        # CAPA for this site
        capas = [c for c in _repo.all("capa_records") if c["site_id"] == site_id]
        capa_id = capas[0]["capa_id"] if capas else None

        self._send_json(200, {
            **dev,
            "protocol_rule": protocol_rule,
            "risk_contribution": risk_contribution,
            "related_deviations": related,
            "affected_patient_count": affected_patient_count,
            "capa_id": capa_id,
        })

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
        guard = self._check_blacklist_guard(site_id, sess)
        if guard:
            self._send_json(guard[0], guard[1])
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
        guard = self._check_blacklist_guard(record["site_id"], sess)
        if guard:
            self._send_json(guard[0], guard[1])
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
            sid = site["site_id"]
            existing = _repo.find_one("risk_scores", "site_id", sid)
            prev = existing["current_score"] if existing else 0
            new_risk = calculate_site_risk(sid, deviations, prev)
            new_risk["calculated_at"] = datetime.now(timezone.utc).isoformat()
            if existing:
                _repo.update("risk_scores", "site_id", sid, new_risk)
            else:
                _repo.insert("risk_scores", new_risk)
            # ── Automatic blacklist evaluation on risk recalculation ──
            score = new_risk["current_score"]
            was_blacklisted = site.get("is_blacklisted", False)
            bl = evaluate_blacklist(sid, score, site)
            if bl["is_blacklisted"] and not was_blacklisted:
                _repo.update("sites", "site_id", sid, bl)
                _audit(sess["user_id"], "SITE_BLACKLISTED", "sites", sid,
                       metadata={"site_id": sid, "risk_score": score,
                                 "threshold": SITE_BLACKLIST_RISK_THRESHOLD,
                                 "reason": bl["blacklist_reason"],
                                 "blacklisted_by": "SYSTEM",
                                 "source": "AUTOMATIC_RISK_THRESHOLD"})
            # If already blacklisted, do not re-write or create duplicate audit
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

    # ── search ────────────────────────────────────────────────────────────────

    def _search(self, sess: dict, qs: dict) -> None:
        q = (qs.get("q") or [""])[0].strip().lower()
        if not q:
            self._send_json(200, {"sites": [], "patients": [], "deviations": [], "capas": [], "rules": []})
            return

        is_coord = sess["role"] == "SITE_COORDINATOR"
        coord_site = sess.get("site_id")

        # Sites
        sites_results = []
        if not is_coord:
            for s in _repo.all("sites"):
                if q in s.get("site_id", "").lower() or q in s.get("name", "").lower() or q in s.get("location", "").lower():
                    sites_results.append({
                        "id": s["site_id"],
                        "label": s["site_id"] + " — " + s.get("name", ""),
                        "sublabel": s.get("location", ""),
                        "type": "site",
                    })
                    if len(sites_results) >= 5:
                        break

        # Patients
        patients_results = []
        for p in _repo.all("patients"):
            if is_coord and p.get("site_id") != coord_site:
                continue
            if q in p.get("patient_id", "").lower():
                patients_results.append({
                    "id": p["patient_id"],
                    "label": p["patient_id"],
                    "sublabel": p.get("site_id", ""),
                    "type": "patient",
                })
                if len(patients_results) >= 5:
                    break

        # Deviations
        deviations_results = []
        for d in _repo.all("deviations"):
            if is_coord and d.get("site_id") != coord_site:
                continue
            if q in d.get("deviation_id", "").lower() or q in d.get("type", "").lower():
                deviations_results.append({
                    "id": d["deviation_id"],
                    "label": d["deviation_id"],
                    "sublabel": d.get("type", "").replace("_", " ").title() + " at " + d.get("site_id", ""),
                    "type": "deviation",
                })
                if len(deviations_results) >= 5:
                    break

        # CAPAs
        capas_results = []
        for c in _repo.all("capa_records"):
            if is_coord and c.get("site_id") != coord_site:
                continue
            if q in c.get("capa_id", "").lower() or q in c.get("problem_statement", "").lower():
                capas_results.append({
                    "id": c["capa_id"],
                    "label": c["capa_id"],
                    "sublabel": c.get("problem_statement", "")[:60],
                    "type": "capa",
                })
                if len(capas_results) >= 5:
                    break

        # Protocol rules (all roles can search)
        rules_results = []
        for rule in _repo.all("protocol_rules"):
            if q in rule.get("rule_id", "").lower() or q in rule.get("name", "").lower() or q in rule.get("domain", "").lower():
                rules_results.append({
                    "id": rule["rule_id"],
                    "label": rule["rule_id"] + " — " + rule.get("name", ""),
                    "sublabel": rule.get("domain", ""),
                    "type": "rule",
                })
                if len(rules_results) >= 5:
                    break

        self._send_json(200, {
            "sites": sites_results,
            "patients": patients_results,
            "deviations": deviations_results,
            "capas": capas_results,
            "rules": rules_results,
        })

    # ── notifications ─────────────────────────────────────────────────────────

    def _notifications(self, sess: dict) -> None:
        risk_scores = _repo.all("risk_scores")
        capa_records = _repo.all("capa_records")
        deviations = _repo.all("deviations")

        is_coord = sess["role"] == "SITE_COORDINATOR"
        coord_site = sess.get("site_id")

        if is_coord:
            risk_scores = [r for r in risk_scores if r.get("site_id") == coord_site]
            capa_records = [c for c in capa_records if c.get("site_id") == coord_site]
            deviations = [d for d in deviations if d.get("site_id") == coord_site]

        notifications = []

        # HIGH risk + WORSENING sites
        for r in risk_scores:
            if r.get("risk_level") == "HIGH" and r.get("trend") == "WORSENING":
                sid = r["site_id"]
                nid = "risk_" + sid
                notifications.append({
                    "id": nid,
                    "type": "risk_increase",
                    "title": f"Risk increasing at Site {sid}",
                    "message": f"Site {sid} risk score is {r.get('current_score', 0)}/100 and worsening (predicted: {r.get('predicted_score', r.get('current_score', 0))}).",
                    "site_id": sid,
                    "resource_id": sid,
                    "link_page": "site-detail",
                    "level": "high",
                })

        # Open/In-progress CAPAs
        for c in capa_records:
            if c.get("status") in ("OPEN", "IN_PROGRESS"):
                cid = c.get("capa_id", "")
                sid = c.get("site_id", "")
                notifications.append({
                    "id": "capa_" + cid,
                    "type": "capa_due",
                    "title": f"CAPA {cid} requires attention",
                    "message": f"CAPA {cid} at Site {sid} is {c.get('status', 'OPEN')}.",
                    "site_id": sid,
                    "resource_id": cid,
                    "link_page": "capa-detail",
                    "level": "medium",
                })

        # Major deviations
        major_devs = sorted(
            [d for d in deviations if d.get("severity") == "MAJOR"],
            key=lambda x: x.get("detected_at", ""),
            reverse=True,
        )
        seen_sites: set[str] = set()
        for d in major_devs:
            sid = d.get("site_id", "")
            if sid in seen_sites:
                continue
            seen_sites.add(sid)
            notifications.append({
                "id": "major_dev_" + d.get("deviation_id", ""),
                "type": "major_deviation",
                "title": f"Major deviation detected at Site {sid}",
                "message": f"Deviation {d.get('deviation_id', '')} ({d.get('type', '').replace('_', ' ').title()}) detected on {d.get('detected_at', '')[:10]}.",
                "site_id": sid,
                "resource_id": d.get("deviation_id", ""),
                "link_page": "deviation-detail",
                "level": "high",
            })

        # Return newest first, max 10
        self._send_json(200, notifications[:10])



# ─── entry point ──────────────────────────────────────────────────────────────

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each request in a separate thread so parallel API calls don't queue."""
    daemon_threads = True


def run_server() -> None:
    server = ThreadedHTTPServer((settings.host, settings.port), Handler)
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
