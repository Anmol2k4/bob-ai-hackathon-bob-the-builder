import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).parent

SITES = [
    {"id": "S037", "status": "critical", "risk": 87, "velocity": 13, "concentration": 72, "peer": 2.1, "trend": [49, 55, 61, 70, 79, 87]},
    {"id": "S021", "status": "high", "risk": 73, "velocity": 1, "concentration": 48, "peer": 1.4, "trend": [75, 74, 74, 73, 73, 73]},
    {"id": "S014", "status": "watch", "risk": 52, "velocity": -8, "concentration": 39, "peer": 1.0, "trend": [71, 67, 63, 59, 55, 52]},
    {"id": "S009", "status": "stable", "risk": 24, "velocity": 0, "concentration": 31, "peer": 0.6, "trend": [23, 24, 24, 23, 24, 24]},
    {"id": "S044", "status": "watch", "risk": 46, "velocity": 9, "concentration": 28, "peer": 0.9, "trend": [23, 27, 31, 36, 41, 46]},
]

SITE_DETAIL = {
    "site_id": "S037",
    "risk_index": 87,
    "status": "critical",
    "velocity": 13,
    "acceleration": 5,
    "forecast": 93,
    "peer_relative_rate": 2.1,
    "risk_concentration": 0.72,
    "decision_confidence": "High",
    "data_quality": "5 monitoring periods / complete hero-site history",
    "drivers": [
        {"label": "V3 scheduling", "share": 72, "count": 7, "rule": "R-03", "detail": "Visit window exceeded by more than 24 hours"},
        {"label": "Late lab processing", "share": 18, "count": 2, "rule": "R-06", "detail": "Safety lab result entered after the review window"},
        {"label": "Other verified rules", "share": 10, "count": 1, "rule": "R-08", "detail": "Missing administration note"},
    ],
    "evidence": [
        {"id": "EV-037-07", "period": "M05", "patient": "P-118", "rule": "R-03", "finding": "V3 visit 31 hours late"},
        {"id": "EV-037-06", "period": "M05", "patient": "P-104", "rule": "R-03", "finding": "V3 visit 28 hours late"},
        {"id": "EV-037-04", "period": "M04", "patient": "P-118", "rule": "R-03", "finding": "V3 visit 26 hours late"},
        {"id": "EV-037-02", "period": "M03", "patient": "P-091", "rule": "R-06", "finding": "Lab result entered 19 hours late"},
    ],
}


def json_response(handler, payload, status=200):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/overview":
            json_response(self, {"sites": SITES, "period": "M05", "synthetic": True, "verified_rules": 9, "open_deviations": 87, "emerging_sites": 2})
            return
        if path == "/api/sites/S037/intelligence":
            json_response(self, SITE_DETAIL)
            return
        if path == "/api/bob/investigate":
            json_response(self, {"answer": "S037 is becoming risky because verified V3 scheduling deviations are accelerating and now account for 72% of its burden. The site is at 2.1x the synthetic peer median, with a high-confidence five-period evidence chain.", "sources": ["Risk Engine", "Evidence Store", "Rule R-03"]})
            return
        if path == "/":
            self.serve_file(ROOT / "static" / "index.html", "text/html")
            return
        if path.startswith("/static/"):
            file_path = ROOT / path.removeprefix("/static/")
            content_type = "text/css" if file_path.suffix == ".css" else "application/javascript"
            self.serve_file(file_path, content_type)
            return
        json_response(self, {"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/sites/S037/simulate":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            reduction = max(0, min(100, int(payload.get("reduction", 30))))
            new_risk = round(SITE_DETAIL["risk_index"] - (reduction * 0.34))
            json_response(self, {"reduction": reduction, "current_risk": SITE_DETAIL["risk_index"], "projected_risk": new_risk, "status": "watch" if new_risk < 60 else "high", "impact": f"{reduction}% fewer R-03 deviations removes the dominant risk driver."})
            return
        json_response(self, {"error": "Not found"}, 404)

    def serve_file(self, file_path, content_type):
        try:
            body = file_path.read_bytes()
        except FileNotFoundError:
            json_response(self, {"error": "File not found"}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), AppHandler)
    print("Clinical Trial Risk Intelligence Copilot: http://127.0.0.1:8000")
    server.serve_forever()