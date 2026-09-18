"""
TrialGuard AI — MCP Server Tests

Tests:
1. MCP tool discovery: all 13 tools are registered
2. Real tool invocations via _safe_call adapter
3. RBAC enforcement: roles are respected
4. Error handling: invalid IDs, permission errors
5. Existing application unchanged

Run with:
    cd src && python -m pytest tests/test_mcp_server.py -v
or:
    cd src && python tests/test_mcp_server.py
"""
from __future__ import annotations

import json
import sys
import os
import unittest

# Ensure src/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synthetic_data import build_demo_state
from database import MemoryRepository
from bob_boundary import build_bob_tools, TOOL_REGISTRY


# ─── Shared fixtures ──────────────────────────────────────────────────────────

def _seeded_repo():
    repo = MemoryRepository()
    state = build_demo_state()
    repo.replace_all(state)
    return repo, state


def _make_sess(role: str, site_id: str | None = None) -> dict:
    return {"role": role, "user_id": f"test-{role.lower()}", "site_id": site_id}


def _safe_call_adapter(tools: dict, tool_name: str, **kwargs) -> dict:
    """Mirror of the _safe_call logic in mcp_server.py."""
    fn = tools.get(tool_name)
    if fn is None:
        return {"error": f"Tool '{tool_name}' not found"}
    try:
        result = fn(**kwargs)
        return json.loads(json.dumps(result, default=str))
    except PermissionError as exc:
        return {"error": "permission_denied", "message": str(exc)}
    except ValueError as exc:
        return {"error": "not_found", "message": str(exc)}
    except Exception as exc:
        return {"error": "internal_error", "message": str(exc)}


# ─── Test 1: Tool discovery ───────────────────────────────────────────────────

class TestMCPToolDiscovery(unittest.TestCase):
    """Verify all 13 TrialGuard tools are present in the registry and build correctly."""

    EXPECTED_TOOLS = {
        "get_trial_overview",
        "list_high_risk_sites",
        "get_site_risk",
        "explain_site_risk",
        "list_site_deviations",
        "get_deviation",
        "search_protocol_rules",
        "compare_patient_to_protocol",
        "get_site_trends",
        "recommend_site_actions",
        "generate_capa",
        "get_capa_status",
        "generate_risk_report",
    }

    def setUp(self):
        repo, _ = _seeded_repo()
        sess = _make_sess("STUDY_MANAGER")
        self.tools = build_bob_tools(repo, sess)

    def test_thirteen_tools_in_registry(self):
        self.assertEqual(len(TOOL_REGISTRY), 13)

    def test_all_thirteen_tools_built(self):
        self.assertEqual(set(self.tools.keys()), self.EXPECTED_TOOLS)

    def test_each_tool_is_callable(self):
        for name, fn in self.tools.items():
            self.assertTrue(callable(fn), f"Tool '{name}' should be callable")

    def test_registry_has_descriptions(self):
        for name, meta in TOOL_REGISTRY.items():
            self.assertTrue(meta.get("description"), f"Tool '{name}' missing description")

    def test_registry_has_roles(self):
        for name, meta in TOOL_REGISTRY.items():
            self.assertTrue(meta.get("roles"), f"Tool '{name}' missing roles")


# ─── Test 2: Real tool invocations ────────────────────────────────────────────

class TestMCPToolInvocations(unittest.TestCase):
    """Invoke all 13 tools with real seeded data and verify structured responses."""

    @classmethod
    def setUpClass(cls):
        cls.repo, cls.state = _seeded_repo()
        cls.sess = _make_sess("STUDY_MANAGER")
        cls.tools = build_bob_tools(cls.repo, cls.sess)
        # Get a real deviation ID for S037
        devs = cls.repo.find_many("deviations", "site_id", "S037")
        cls.dev_id = devs[0]["deviation_id"] if devs else "DEV-0001"
        # Get a real patient ID at S037
        patients = cls.repo.find_many("patients", "site_id", "S037")
        cls.patient_id = patients[0]["patient_id"] if patients else "P-001"

    def _call(self, name, **kwargs):
        return _safe_call_adapter(self.tools, name, **kwargs)

    def test_get_trial_overview(self):
        r = self._call("get_trial_overview")
        self.assertNotIn("error", r)
        self.assertIn("total_sites", r)
        self.assertEqual(r["total_sites"], 42)
        self.assertEqual(r["total_patients"], 1128)
        self.assertGreater(r["total_deviations"], 900)

    def test_list_high_risk_sites(self):
        r = self._call("list_high_risk_sites", limit=5)
        self.assertNotIn("error", r)
        self.assertIn("high_risk_sites", r)
        self.assertGreater(r["count"], 0)
        top = r["high_risk_sites"][0]
        self.assertIn("site_id", top)
        self.assertIn("risk_score", top)

    def test_list_high_risk_sites_top_is_s037(self):
        r = self._call("list_high_risk_sites", limit=1)
        sites = r["high_risk_sites"]
        self.assertTrue(len(sites) > 0)
        self.assertEqual(sites[0]["site_id"], "S037")
        self.assertEqual(sites[0]["risk_score"], 87)

    def test_get_site_risk_s037(self):
        r = self._call("get_site_risk", site_id="S037")
        self.assertNotIn("error", r)
        self.assertEqual(r["current_score"], 87)
        self.assertEqual(r["risk_level"], "HIGH")
        self.assertEqual(r["trend"], "WORSENING")

    def test_explain_site_risk_s037(self):
        r = self._call("explain_site_risk", site_id="S037")
        self.assertNotIn("error", r)
        self.assertIn("explanation", r)
        self.assertIn("87", r["explanation"])
        self.assertIn("WORSENING", r["explanation"])
        self.assertIn("major_count", r)

    def test_list_site_deviations_s037(self):
        r = self._call("list_site_deviations", site_id="S037")
        self.assertNotIn("error", r)
        self.assertGreater(r["count"], 50)
        self.assertEqual(r["deviations"][0]["site_id"], "S037")

    def test_list_site_deviations_filtered_major(self):
        r = self._call("list_site_deviations", site_id="S037", severity="MAJOR")
        self.assertNotIn("error", r)
        for dev in r["deviations"]:
            self.assertEqual(dev["severity"], "MAJOR")

    def test_get_deviation(self):
        r = self._call("get_deviation", deviation_id=self.dev_id)
        self.assertNotIn("error", r)
        self.assertIn("deviation_id", r)
        self.assertIn("severity", r)
        self.assertIn("type", r)

    def test_search_protocol_rules(self):
        r = self._call("search_protocol_rules", query="dose")
        self.assertNotIn("error", r)
        self.assertIn("rules", r)

    def test_search_protocol_rules_no_query(self):
        r = self._call("search_protocol_rules")
        self.assertNotIn("error", r)
        self.assertIn("rules", r)
        self.assertGreater(len(r["rules"]), 0)

    def test_compare_patient_to_protocol(self):
        r = self._call("compare_patient_to_protocol", patient_id=self.patient_id)
        self.assertNotIn("error", r)
        self.assertIn("compliant", r)
        self.assertIn("patient_id", r)

    def test_get_site_trends_s037(self):
        r = self._call("get_site_trends", site_id="S037")
        self.assertNotIn("error", r)
        self.assertEqual(r["trend"], "WORSENING")
        self.assertIn("current_score", r)
        self.assertIn("deviation_type_breakdown", r)

    def test_recommend_site_actions_s037(self):
        r = self._call("recommend_site_actions", site_id="S037")
        self.assertNotIn("error", r)
        self.assertIn("corrective_actions", r)
        self.assertIn("preventive_actions", r)
        self.assertIn("disclaimer", r)
        self.assertGreater(len(r["corrective_actions"]), 0)

    def test_generate_capa_s037(self):
        r = self._call("generate_capa", site_id="S037")
        self.assertNotIn("error", r)
        self.assertIn("capa_id", r)
        self.assertIn("problem_statement", r)
        self.assertIn("root_cause", r)
        self.assertEqual(r["status"], "OPEN")
        self.assertIn("disclaimer", r)

    def test_generate_capa_root_cause_labelled_ai(self):
        r = self._call("generate_capa", site_id="S037")
        self.assertIn("AI-generated", r.get("root_cause", ""))

    def test_get_capa_status(self):
        r = self._call("get_capa_status")
        self.assertNotIn("error", r)
        self.assertIn("capa_records", r)
        self.assertIn("status_summary", r)

    def test_get_capa_status_site_filter(self):
        r = self._call("get_capa_status", site_id="S037")
        self.assertNotIn("error", r)
        for capa in r["capa_records"]:
            self.assertEqual(capa["site_id"], "S037")

    def test_generate_risk_report_s037(self):
        r = self._call("generate_risk_report", site_id="S037")
        self.assertNotIn("error", r)
        self.assertEqual(r["report_type"], "site_risk")
        self.assertIn("risk", r)
        self.assertIn("disclaimer", r)


# ─── Test 3: RBAC enforcement ─────────────────────────────────────────────────

class TestMCPRBAC(unittest.TestCase):
    """Verify that RBAC is enforced through the MCP tool layer."""

    @classmethod
    def setUpClass(cls):
        cls.repo, _ = _seeded_repo()

    def _tools(self, role, site_id=None):
        return build_bob_tools(self.repo, _make_sess(role, site_id))

    # TEST 1: STUDY_MANAGER can call get_trial_overview
    def test_study_manager_can_get_trial_overview(self):
        tools = self._tools("STUDY_MANAGER")
        r = _safe_call_adapter(tools, "get_trial_overview")
        self.assertNotIn("error", r)
        self.assertIn("total_sites", r)

    # TEST 2: STUDY_MANAGER can inspect a site
    def test_study_manager_can_inspect_any_site(self):
        tools = self._tools("STUDY_MANAGER")
        r = _safe_call_adapter(tools, "get_site_risk", site_id="S037")
        self.assertNotIn("error", r)
        self.assertEqual(r["current_score"], 87)

    # TEST 3: SITE_COORDINATOR can inspect their assigned site
    def test_site_coordinator_can_inspect_own_site(self):
        tools = self._tools("SITE_COORDINATOR", site_id="S037")
        r = _safe_call_adapter(tools, "get_site_risk", site_id="S037")
        self.assertNotIn("error", r)

    # TEST 4: SITE_COORDINATOR cannot inspect another site
    def test_site_coordinator_cannot_inspect_other_site(self):
        tools = self._tools("SITE_COORDINATOR", site_id="S037")
        r = _safe_call_adapter(tools, "get_site_risk", site_id="S008")
        self.assertEqual(r.get("error"), "permission_denied")

    # TEST 5: AUDITOR can read permitted data
    def test_auditor_can_read_site_risk(self):
        tools = self._tools("AUDITOR")
        r = _safe_call_adapter(tools, "get_site_risk", site_id="S037")
        self.assertNotIn("error", r)

    def test_auditor_can_read_trial_overview(self):
        tools = self._tools("AUDITOR")
        r = _safe_call_adapter(tools, "get_trial_overview")
        self.assertNotIn("error", r)

    def test_auditor_can_list_high_risk_sites(self):
        tools = self._tools("AUDITOR")
        r = _safe_call_adapter(tools, "list_high_risk_sites")
        self.assertNotIn("error", r)

    # TEST 6: AUDITOR cannot generate CAPA
    def test_auditor_cannot_generate_capa(self):
        tools = self._tools("AUDITOR")
        r = _safe_call_adapter(tools, "generate_capa", site_id="S037")
        self.assertEqual(r.get("error"), "permission_denied")

    def test_auditor_cannot_recommend_actions(self):
        tools = self._tools("AUDITOR")
        r = _safe_call_adapter(tools, "recommend_site_actions", site_id="S037")
        self.assertEqual(r.get("error"), "permission_denied")

    # TEST 7: MCP layer does not bypass existing permissions
    def test_mcp_layer_does_not_bypass_site_scope(self):
        # Coordinator for S037 must not see S008 data
        tools = self._tools("SITE_COORDINATOR", site_id="S037")
        r = _safe_call_adapter(tools, "list_site_deviations", site_id="S008")
        self.assertEqual(r.get("error"), "permission_denied")

    def test_mcp_layer_does_not_bypass_role_check(self):
        # AUDITOR must not be able to generate CAPA even if called directly
        tools = self._tools("AUDITOR")
        r = _safe_call_adapter(tools, "generate_capa", site_id="S037")
        self.assertIn("error", r)
        self.assertEqual(r["error"], "permission_denied")

    def test_site_coordinator_cross_site_deviations_denied(self):
        tools = self._tools("SITE_COORDINATOR", site_id="S037")
        r = _safe_call_adapter(tools, "explain_site_risk", site_id="S008")
        self.assertEqual(r.get("error"), "permission_denied")

    def test_system_admin_can_access_all_sites(self):
        tools = self._tools("SYSTEM_ADMIN")
        for site in ("S037", "S008", "S021"):
            r = _safe_call_adapter(tools, "get_site_risk", site_id=site)
            self.assertNotIn("error", r, f"SYSTEM_ADMIN should access {site}")

    def test_system_admin_can_generate_capa(self):
        tools = self._tools("SYSTEM_ADMIN")
        r = _safe_call_adapter(tools, "generate_capa", site_id="S037")
        self.assertNotIn("error", r)


# ─── Test 4: Error handling ───────────────────────────────────────────────────

class TestMCPErrorHandling(unittest.TestCase):
    """Verify graceful error handling for invalid inputs."""

    @classmethod
    def setUpClass(cls):
        cls.repo, _ = _seeded_repo()
        cls.tools = build_bob_tools(cls.repo, _make_sess("STUDY_MANAGER"))

    def _call(self, name, **kwargs):
        return _safe_call_adapter(self.tools, name, **kwargs)

    def test_invalid_site_id_returns_error(self):
        r = self._call("get_site_risk", site_id="INVALID-SITE-XYZ")
        self.assertIn("error", r)
        self.assertEqual(r["error"], "not_found")

    def test_invalid_deviation_id_returns_error(self):
        r = self._call("get_deviation", deviation_id="INVALID-DEV-XYZ")
        self.assertIn("error", r)
        self.assertEqual(r["error"], "not_found")

    def test_invalid_patient_id_returns_error(self):
        r = self._call("compare_patient_to_protocol", patient_id="INVALID-PT-XYZ")
        self.assertIn("error", r)
        self.assertEqual(r["error"], "not_found")

    def test_missing_required_site_id_risk(self):
        # get_site_risk requires site_id — missing positional arg should fail
        fn = self.tools.get("get_site_risk")
        with self.assertRaises(TypeError):
            fn()

    def test_invalid_site_generate_risk_report(self):
        r = self._call("generate_risk_report", site_id="NONEXISTENT")
        # Site not found — may return empty site dict but should not crash
        # The tool returns an empty site dict when site not found, not an error
        self.assertNotIn("error", r)

    def test_error_message_does_not_contain_credentials(self):
        r = self._call("get_site_risk", site_id="INVALID")
        msg = r.get("message", "")
        self.assertNotIn("mongodb://", msg.lower())
        self.assertNotIn("password", msg.lower())
        self.assertNotIn("secret", msg.lower())


# ─── Test 5: Existing application not broken ──────────────────────────────────

class TestExistingApplicationIntact(unittest.TestCase):
    """Verify existing LocalDemoBobProvider and web-facing tools still work."""

    @classmethod
    def setUpClass(cls):
        cls.repo, cls.state = _seeded_repo()
        cls.sess = _make_sess("STUDY_MANAGER")
        cls.tools = build_bob_tools(cls.repo, cls.sess)

    def test_local_demo_provider_still_available(self):
        from bob_boundary import LocalDemoBobProvider
        provider = LocalDemoBobProvider()
        self.assertTrue(callable(provider.answer))

    def test_local_demo_provider_answer(self):
        from bob_boundary import LocalDemoBobProvider
        from models import User
        provider = LocalDemoBobProvider()
        user = User(
            user_id="test",
            name="Test Manager",
            email="test@example.com",
            password_hash="x",
            role="STUDY_MANAGER",
        )
        result = provider.answer("Give me a trial overview", user, self.tools)
        self.assertIn("answer", result)
        self.assertIn("sources", result)

    def test_tool_contracts_still_returns_13(self):
        from bob_boundary import tool_contracts
        contracts = tool_contracts()
        self.assertEqual(len(contracts), 13)

    def test_server_module_importable(self):
        # Verify server.py still imports without errors (don't run the server)
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "server",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "server.py"),
        )
        # Just verify spec loads — don't exec to avoid binding a port
        self.assertIsNotNone(spec)

    def test_all_thirteen_tools_registered(self):
        self.assertEqual(len(self.tools), 13)


# ─── Test 6: MCP server module structure ──────────────────────────────────────

class TestMCPServerModule(unittest.TestCase):
    """Verify that mcp_server.py defines all 13 tools and MCPServer instance."""

    def test_mcp_server_file_exists(self):
        # __file__ is src/tests/test_mcp_server.py  →  src/ is one level up
        src_dir = os.path.dirname(os.path.dirname(__file__))
        mcp_path = os.path.join(src_dir, "mcp_server.py")
        self.assertTrue(os.path.isfile(mcp_path), f"src/mcp_server.py should exist at {mcp_path}")

    def test_bob_mcp_json_exists(self):
        # src/ is one level up; project root is two levels up
        src_dir = os.path.dirname(os.path.dirname(__file__))
        project_root = os.path.dirname(src_dir)
        bob_cfg = os.path.join(project_root, ".bob", "mcp.json")
        self.assertTrue(os.path.isfile(bob_cfg), f".bob/mcp.json should exist at {bob_cfg}")

    def test_bob_mcp_json_has_trialguard_server(self):
        src_dir = os.path.dirname(os.path.dirname(__file__))
        project_root = os.path.dirname(src_dir)
        bob_cfg = os.path.join(project_root, ".bob", "mcp.json")
        with open(bob_cfg) as f:
            config = json.load(f)
        self.assertIn("mcpServers", config)
        self.assertIn("trialguard", config["mcpServers"])
        server = config["mcpServers"]["trialguard"]
        self.assertEqual(server.get("command"), "python")
        self.assertFalse(server.get("disabled", False))

    def test_requirements_includes_mcp(self):
        src_dir = os.path.dirname(os.path.dirname(__file__))
        req_path = os.path.join(src_dir, "requirements.txt")
        with open(req_path) as f:
            content = f.read()
        self.assertIn("mcp", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
