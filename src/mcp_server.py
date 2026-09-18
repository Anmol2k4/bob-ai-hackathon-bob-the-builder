"""
TrialGuard AI — IBM Bob MCP Server

Exposes the 13 TrialGuard tool contracts to IBM Bob via the Model Context Protocol (MCP).
This file is a thin adapter only — all business logic lives in bob_boundary.py, services.py,
engines.py and the repository layer.

Architecture:
    IBM Bob (MCP client)
        ↓  STDIO
    MCPServer  ← this file
        ↓
    build_bob_tools(repo, sess)   ← bob_boundary.py
        ↓
    Existing TrialGuard services  ← services.py, engines.py
        ↓
    MongoDB / in-memory repository  ← database.py

Identity is configured via environment variables:
    TRIALGUARD_BOB_ROLE       (default: STUDY_MANAGER)
    TRIALGUARD_BOB_USER_ID    (default: bob-demo)
    TRIALGUARD_BOB_SITE_ID    (default: empty — cross-site access for STUDY_MANAGER)

Usage:
    python src/mcp_server.py

Or via IBM Bob mcp.json configuration.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

# Ensure src/ is on the path when launched directly from project root
_SRC = os.path.dirname(os.path.abspath(__file__))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcp.server.mcpserver import MCPServer

from bob_boundary import build_bob_tools, TOOL_REGISTRY
from database import create_repository

# ─── Logging — use stderr so stdout stays clean for MCP protocol ─────────────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [TrialGuard-MCP] %(levelname)s %(message)s",
)
logger = logging.getLogger("trialguard_mcp")

# ─── Identity from environment ────────────────────────────────────────────────

_ROLE = os.environ.get("TRIALGUARD_BOB_ROLE", "STUDY_MANAGER").strip()
_USER_ID = os.environ.get("TRIALGUARD_BOB_USER_ID", "bob-demo").strip()
_SITE_ID = os.environ.get("TRIALGUARD_BOB_SITE_ID", "").strip() or None

# Build the session dict in the same format expected by build_bob_tools()
_SESSION: dict = {
    "role": _ROLE,
    "user_id": _USER_ID,
    "site_id": _SITE_ID,
}

# ─── Repository and tool factory ──────────────────────────────────────────────

logger.info(
    "Initialising TrialGuard repository (role=%s, user=%s, site=%s) ...",
    _ROLE,
    _USER_ID,
    _SITE_ID or "ALL",
)

_repo = create_repository()
logger.info("Repository backend: %s", _repo.backend)

_tools = build_bob_tools(_repo, _SESSION)

# ─── Longer, AI-useful descriptions (overrides the short registry descriptions) ─

_DESCRIPTIONS: dict[str, str] = {
    "get_trial_overview": (
        "Return trial-level KPIs for the entire clinical trial, including total sites, "
        "total patients, total deviations, major deviation count, high-risk site count, "
        "and open CAPA records. Use this when the user asks for a summary, overview, or "
        "high-level status of the trial."
    ),
    "list_high_risk_sites": (
        "Return a ranked list of high-risk clinical trial sites with their current risk "
        "score, risk level, trend direction, leading indicators, and predicted score. "
        "Use this when the user asks which sites are most at risk, or to identify sites "
        "requiring immediate attention."
    ),
    "get_site_risk": (
        "Retrieve the current risk assessment for a specific clinical trial site, including "
        "risk score (0-100), risk level (LOW/MEDIUM/HIGH), trend direction "
        "(IMPROVING/STABLE/WORSENING), leading indicators, predicted score, and contributing "
        "risk drivers. Use this when investigating why a site is high risk or when assessing "
        "current site status."
    ),
    "explain_site_risk": (
        "Return a detailed, evidence-backed explanation of why a site's risk score is at its "
        "current level. Includes risk score, trend, leading indicators, major deviation count, "
        "most frequent deviation types, and a plain-language explanation grounded in database "
        "records. Use this when the user asks why a site is high risk or what is driving risk."
    ),
    "list_site_deviations": (
        "List all protocol deviations recorded for an authorized clinical trial site, optionally "
        "filtered by severity (MAJOR/MINOR/ADMINISTRATIVE). Returns deviation records including "
        "type, severity, evidence, and detection date. Use this when the user asks about "
        "deviations at a specific site or wants to see the specific protocol violations."
    ),
    "get_deviation": (
        "Return the complete record for a single protocol deviation by ID, including full "
        "evidence, severity classification with per-factor scores, associated rule, and "
        "protocol reference. Use this when investigating a specific deviation in detail."
    ),
    "search_protocol_rules": (
        "Search the TrialGuard trial protocol (TG-101) rules by keyword or domain. Returns "
        "matching rules with their identifiers, descriptions, and compliance requirements. "
        "Use this when the user asks about protocol requirements, specific rules, or wants to "
        "understand what the trial protocol requires."
    ),
    "compare_patient_to_protocol": (
        "Compare a specific synthetic patient record against the trial protocol eligibility "
        "criteria and flag any violations. Returns compliance status and any identified issues. "
        "Use this when checking whether a patient meets protocol eligibility criteria."
    ),
    "get_site_trends": (
        "Return deviation trend data for a site, including current and predicted risk score, "
        "trend direction, historical sparkline, and breakdown of deviation types. Use this when "
        "the user asks whether a site's risk is worsening, improving, or isolated, or to "
        "understand the trajectory of a site's risk over time."
    ),
    "recommend_site_actions": (
        "Generate recommended corrective and preventive actions for a site based on its "
        "current deviation profile and risk level. Returns specific, deviation-type-appropriate "
        "action lists with a disclaimer that qualified review is required. Use this after "
        "investigating a site and when the user asks what should be done to address the risk."
    ),
    "generate_capa": (
        "Generate a CAPA (Corrective and Preventive Action) draft for a site based on its "
        "actual deviation records. Facts (deviation IDs, counts, types, severities) come from "
        "TrialGuard data; root cause and action recommendations are AI-generated hypotheses "
        "requiring qualified clinical review. Use only after investigating the relevant site "
        "and deviations. The output clearly distinguishes factual evidence from recommendations."
    ),
    "get_capa_status": (
        "Return CAPA records and their current status (OPEN/IN_PROGRESS/CLOSED) for a site or "
        "across the trial. Includes a status summary count. Use this when the user asks about "
        "existing corrective actions or wants to track CAPA progress."
    ),
    "generate_risk_report": (
        "Generate a structured risk report payload for a site, including site profile, current "
        "risk score, deviation counts, and open CAPA count. Use this when the user asks for a "
        "risk report or wants a comprehensive overview of a site's risk situation. The report "
        "contains synthetic data only and is not for clinical or regulatory use."
    ),
}

# ─── MCP server ───────────────────────────────────────────────────────────────

mcp = MCPServer(
    name="trialguard",
    title="TrialGuard AI — Clinical Trial Risk Monitor",
    description=(
        "Exposes 13 TrialGuard tools for clinical trial risk monitoring, protocol deviation "
        "detection, site risk assessment, CAPA generation, and evidence-backed investigation. "
        "All tools enforce RBAC and site-scope authorization. Data is synthetic demo data only."
    ),
    version="1.0.0",
)


def _safe_call(tool_name: str, **kwargs) -> str:
    """Call a TrialGuard tool and serialize the result, or return a structured error."""
    fn = _tools.get(tool_name)
    if fn is None:
        return json.dumps({"error": f"Tool '{tool_name}' not found in TrialGuard tool registry."})
    try:
        result = fn(**kwargs)
        # Remove None values for cleaner output
        cleaned = {k: v for k, v in result.items() if v is not None}
        return json.dumps(cleaned, default=str, indent=2)
    except PermissionError as exc:
        logger.warning("Permission denied for tool '%s': %s", tool_name, exc)
        return json.dumps({"error": "permission_denied", "message": str(exc)})
    except ValueError as exc:
        logger.warning("Value error in tool '%s': %s", tool_name, exc)
        return json.dumps({"error": "not_found", "message": str(exc)})
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in tool '%s'", tool_name)
        return json.dumps({"error": "internal_error", "message": f"Tool execution failed: {type(exc).__name__}"})


# ─── Register all 13 tools ────────────────────────────────────────────────────

@mcp.tool(description=_DESCRIPTIONS["get_trial_overview"])
def get_trial_overview() -> str:
    """Return trial-level KPIs for the entire clinical trial."""
    return _safe_call("get_trial_overview")


@mcp.tool(description=_DESCRIPTIONS["list_high_risk_sites"])
def list_high_risk_sites(limit: int = 10) -> str:
    """Return a ranked list of high-risk clinical trial sites."""
    return _safe_call("list_high_risk_sites", limit=limit)


@mcp.tool(description=_DESCRIPTIONS["get_site_risk"])
def get_site_risk(site_id: str) -> str:
    """Retrieve the current risk assessment for a specific clinical trial site."""
    return _safe_call("get_site_risk", site_id=site_id)


@mcp.tool(description=_DESCRIPTIONS["explain_site_risk"])
def explain_site_risk(site_id: str) -> str:
    """Return a detailed, evidence-backed explanation of why a site's risk score is at its current level."""
    return _safe_call("explain_site_risk", site_id=site_id)


@mcp.tool(description=_DESCRIPTIONS["list_site_deviations"])
def list_site_deviations(site_id: str, severity: str = "") -> str:
    """List all protocol deviations recorded for a clinical trial site."""
    kwargs: dict = {"site_id": site_id}
    if severity:
        kwargs["severity"] = severity
    return _safe_call("list_site_deviations", **kwargs)


@mcp.tool(description=_DESCRIPTIONS["get_deviation"])
def get_deviation(deviation_id: str) -> str:
    """Return the complete record for a single protocol deviation by ID."""
    return _safe_call("get_deviation", deviation_id=deviation_id)


@mcp.tool(description=_DESCRIPTIONS["search_protocol_rules"])
def search_protocol_rules(query: str = "") -> str:
    """Search the TrialGuard trial protocol (TG-101) rules by keyword or domain."""
    return _safe_call("search_protocol_rules", query=query)


@mcp.tool(description=_DESCRIPTIONS["compare_patient_to_protocol"])
def compare_patient_to_protocol(patient_id: str) -> str:
    """Compare a specific synthetic patient record against the trial protocol eligibility criteria."""
    return _safe_call("compare_patient_to_protocol", patient_id=patient_id)


@mcp.tool(description=_DESCRIPTIONS["get_site_trends"])
def get_site_trends(site_id: str) -> str:
    """Return deviation trend data for a clinical trial site."""
    return _safe_call("get_site_trends", site_id=site_id)


@mcp.tool(description=_DESCRIPTIONS["recommend_site_actions"])
def recommend_site_actions(site_id: str) -> str:
    """Generate recommended corrective and preventive actions for a site."""
    return _safe_call("recommend_site_actions", site_id=site_id)


@mcp.tool(description=_DESCRIPTIONS["generate_capa"])
def generate_capa(site_id: str) -> str:
    """Generate a CAPA draft for a site based on its actual deviation records."""
    return _safe_call("generate_capa", site_id=site_id)


@mcp.tool(description=_DESCRIPTIONS["get_capa_status"])
def get_capa_status(site_id: str = "") -> str:
    """Return CAPA records and their current status for a site or across the trial."""
    kwargs: dict = {}
    if site_id:
        kwargs["site_id"] = site_id
    return _safe_call("get_capa_status", **kwargs)


@mcp.tool(description=_DESCRIPTIONS["generate_risk_report"])
def generate_risk_report(site_id: str) -> str:
    """Generate a structured risk report payload for a clinical trial site."""
    return _safe_call("generate_risk_report", site_id=site_id)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(
        "Starting TrialGuard MCP server (13 tools) via STDIO transport. "
        "Role: %s | User: %s | Site scope: %s",
        _ROLE,
        _USER_ID,
        _SITE_ID or "ALL",
    )
    asyncio.run(mcp.run_stdio_async())
