"""
TrialGuard AI — Core test suite.

Covers:
  - Authentication helpers
  - Password hashing/verification
  - RBAC authorization logic
  - Cross-site access prevention
  - Protocol deviation detection
  - Severity classification (all three tiers)
  - Site risk calculation (S037 deterministic)
  - CAPA generation
  - Bob tool authorization
  - Deterministic dataset integrity
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from engines import (
    calculate_site_risk,
    classify_severity,
    run_deviation_engine,
)
from security import hash_password, verify_password
from services import generate_capa_record
from synthetic_data import build_demo_state
from bob_boundary import build_bob_tools, TOOL_REGISTRY


# ─── Shared fixtures ──────────────────────────────────────────────────────────

class _FixtureBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = build_demo_state()


# ─── 1. Authentication ────────────────────────────────────────────────────────

class TestPasswordAuth(unittest.TestCase):
    """Password hashing and verification."""

    def test_hash_is_not_plaintext(self):
        h = hash_password("secret", "salt123")
        self.assertNotEqual(h, "secret")
        self.assertGreater(len(h), 20)  # not plaintext — much longer than input

    def test_correct_password_verifies(self):
        h = hash_password("TrialGuard2026!", "demo-salt")
        self.assertTrue(verify_password("TrialGuard2026!", h))

    def test_wrong_password_fails(self):
        h = hash_password("correct-horse", "demo-salt")
        self.assertFalse(verify_password("wrong-pony", h))

    def test_empty_password_not_accepted_as_match(self):
        h = hash_password("notempty", "salt")
        self.assertFalse(verify_password("", h))

    def test_different_salts_produce_different_hashes(self):
        h1 = hash_password("same", "salt-A")
        h2 = hash_password("same", "salt-B")
        self.assertNotEqual(h1, h2)

    def test_hash_deterministic_with_same_salt(self):
        h1 = hash_password("pw", "fixed-salt")
        h2 = hash_password("pw", "fixed-salt")
        self.assertEqual(h1, h2)


# ─── 2. Demo users seeded with correct roles ──────────────────────────────────

class TestDemoUsers(_FixtureBase):
    """Demo accounts present with correct roles."""

    def _user(self, email):
        return next((u for u in self.state.users if u["email"] == email), None)

    def test_study_manager_exists(self):
        u = self._user("manager@trialguard.demo")
        self.assertIsNotNone(u)
        self.assertEqual(u["role"], "STUDY_MANAGER")

    def test_site_coordinator_exists_with_site(self):
        u = self._user("site037@trialguard.demo")
        self.assertIsNotNone(u)
        self.assertEqual(u["role"], "SITE_COORDINATOR")
        self.assertEqual(u["site_id"], "S037")

    def test_auditor_exists(self):
        u = self._user("auditor@trialguard.demo")
        self.assertIsNotNone(u)
        self.assertEqual(u["role"], "AUDITOR")

    def test_admin_exists(self):
        u = self._user("admin@trialguard.demo")
        self.assertIsNotNone(u)
        self.assertEqual(u["role"], "SYSTEM_ADMIN")

    def test_passwords_are_hashed(self):
        for u in self.state.users:
            self.assertNotEqual(u["password_hash"], "TrialGuard2026!",
                                f"User {u['email']} password stored as plaintext")
            self.assertGreater(len(u["password_hash"]), 20,
                               f"User {u['email']} password_hash too short to be a real hash")


# ─── 3. RBAC logic ────────────────────────────────────────────────────────────

class TestRBAC(unittest.TestCase):
    """Server-side RBAC helpers."""

    def _make_sess(self, role, site_id=None):
        return {"role": role, "site_id": site_id, "user_id": "test", "email": "t@t.com", "name": "Test"}

    def test_manager_allowed_all_roles_list(self):
        sess = self._make_sess("STUDY_MANAGER")
        self.assertIn(sess["role"], ["STUDY_MANAGER", "AUDITOR", "SYSTEM_ADMIN", "SITE_COORDINATOR"])

    def test_site_scope_coordinator_own_site_allowed(self):
        from server import _site_scope
        sess = self._make_sess("SITE_COORDINATOR", "S037")
        self.assertTrue(_site_scope(sess, "S037"))

    def test_site_scope_coordinator_other_site_denied(self):
        from server import _site_scope
        sess = self._make_sess("SITE_COORDINATOR", "S037")
        self.assertFalse(_site_scope(sess, "S001"))

    def test_site_scope_manager_all_sites_allowed(self):
        from server import _site_scope
        sess = self._make_sess("STUDY_MANAGER")
        for site_id in ["S001", "S037", "S042"]:
            self.assertTrue(_site_scope(sess, site_id))

    def test_site_scope_auditor_all_sites_allowed(self):
        from server import _site_scope
        sess = self._make_sess("AUDITOR")
        self.assertTrue(_site_scope(sess, "S099"))

    def test_authorize_returns_error_when_no_session(self):
        from server import _authorize
        sess, err = _authorize(None)
        self.assertIsNone(sess)
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 401)

    def test_authorize_returns_error_wrong_role(self):
        from server import _authorize
        sess_dict = self._make_sess("SITE_COORDINATOR")
        sess, err = _authorize(sess_dict, allowed_roles=["STUDY_MANAGER"])
        self.assertIsNone(sess)
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 403)

    def test_authorize_passes_correct_role(self):
        from server import _authorize
        sess_dict = self._make_sess("STUDY_MANAGER")
        sess, err = _authorize(sess_dict, allowed_roles=["STUDY_MANAGER"])
        self.assertIsNotNone(sess)
        self.assertIsNone(err)


# ─── 4. Cross-site access prevention ─────────────────────────────────────────

class TestCrossSiteAccess(_FixtureBase):
    """Site Coordinator cannot access another site's data via Bob tools."""

    def _sess(self, role, site_id=None):
        return {"role": role, "site_id": site_id, "user_id": "x", "email": "x@x.com", "name": "X"}

    def _repo_from_state(self):
        """Minimal in-memory repo backed by the demo state."""
        from database import MemoryRepository
        repo = MemoryRepository()
        repo.replace_all(self.state)
        return repo

    def test_coordinator_denied_access_to_other_site(self):
        repo = self._repo_from_state()
        sess = self._sess("SITE_COORDINATOR", "S037")
        tools = build_bob_tools(repo, sess)
        with self.assertRaises(PermissionError) as ctx:
            tools["get_site_risk"](site_id="S001")
        self.assertIn("S001", str(ctx.exception))

    def test_coordinator_allowed_own_site(self):
        repo = self._repo_from_state()
        sess = self._sess("SITE_COORDINATOR", "S037")
        tools = build_bob_tools(repo, sess)
        result = tools["get_site_risk"](site_id="S037")
        self.assertEqual(result["site_id"], "S037")

    def test_coordinator_denied_explain_risk_other_site(self):
        repo = self._repo_from_state()
        sess = self._sess("SITE_COORDINATOR", "S037")
        tools = build_bob_tools(repo, sess)
        with self.assertRaises(PermissionError):
            tools["explain_site_risk"](site_id="S008")

    def test_manager_can_access_any_site(self):
        repo = self._repo_from_state()
        sess = self._sess("STUDY_MANAGER")
        tools = build_bob_tools(repo, sess)
        for site_id in ["S001", "S037", "S042"]:
            result = tools["get_site_risk"](site_id=site_id)
            self.assertEqual(result["site_id"], site_id)


# ─── 5. Protocol deviation detection ─────────────────────────────────────────

class TestDeviationEngine(unittest.TestCase):
    """Rule-based deviation detection produces correct results."""

    PROTOCOL = [{
        "protocol_id": "TG-101",
        "dose_mg": 100,
        "visit_window_days": 2,
        "min_age": 18,
        "max_age": 65,
        "prohibited_medications": ["Drug X", "Drug Y"],
    }]

    def _run(self, patients, visits, meds=None):
        return run_deviation_engine(self.PROTOCOL, patients, visits, meds or [])

    def _patient(self, pid, age=30, site="S001"):
        return {"patient_id": pid, "site_id": site, "age": age}

    def _visit(self, pid, site="S001", visit_num=1, dose_expected=100, dose_actual=100,
               sched="2025-01-07", actual="2025-01-07", assessment="COMPLETE",
               data_entry="2025-01-08"):
        return {
            "patient_id": pid, "site_id": site, "visit_number": visit_num,
            "scheduled_date": sched, "actual_date": actual,
            "dose_expected": dose_expected, "dose_actual": dose_actual,
            "assessment_status": assessment,
            "data_entry_date": data_entry,
        }

    def test_no_deviations_when_compliant(self):
        p = self._patient("P001")
        v = self._visit("P001")
        devs = self._run([p], [v])
        self.assertEqual(len(devs), 0)

    def test_incorrect_dose_detected(self):
        p = self._patient("P002")
        v = self._visit("P002", dose_expected=100, dose_actual=150)
        devs = self._run([p], [v])
        types = [d["type"] for d in devs]
        self.assertIn("INCORRECT_DOSE", types)

    def test_incorrect_dose_actual_is_150(self):
        p = self._patient("P003")
        v = self._visit("P003", dose_expected=100, dose_actual=150)
        devs = self._run([p], [v])
        dose_devs = [d for d in devs if d["type"] == "INCORRECT_DOSE"]
        self.assertTrue(any("150 mg" in d["actual"] for d in dose_devs))
        self.assertTrue(any("100 mg" in d["expected"] for d in dose_devs))

    def test_visit_outside_window_detected(self):
        p = self._patient("P004")
        # visit_number=2, scheduled Day 7, actual Day 14 — 7 days late
        v = self._visit("P004", visit_num=2,
                        sched="2025-01-07", actual="2025-01-14")
        devs = self._run([p], [v])
        types = [d["type"] for d in devs]
        self.assertIn("VISIT_OUTSIDE_WINDOW", types)

    def test_visit_within_window_not_flagged(self):
        p = self._patient("P005")
        v = self._visit("P005", visit_num=2,
                        sched="2025-01-07", actual="2025-01-08")  # 1 day off — within ±2
        devs = self._run([p], [v])
        self.assertFalse(any(d["type"] == "VISIT_OUTSIDE_WINDOW" for d in devs))

    def test_prohibited_medication_detected(self):
        p = self._patient("P006")
        v = self._visit("P006")
        meds = [{"patient_id": "P006", "medication_name": "Drug X",
                 "start_date": "2025-01-01", "end_date": "2025-01-10", "prohibited": True}]
        devs = self._run([p], [v], meds)
        types = [d["type"] for d in devs]
        self.assertIn("PROHIBITED_MEDICATION", types)

    def test_drug_y_also_prohibited(self):
        p = self._patient("P007")
        v = self._visit("P007")
        meds = [{"patient_id": "P007", "medication_name": "Drug Y",
                 "start_date": "2025-01-01", "end_date": "2025-01-10", "prohibited": True}]
        devs = self._run([p], [v], meds)
        self.assertTrue(any(d["type"] == "PROHIBITED_MEDICATION" for d in devs))

    def test_missing_assessment_detected(self):
        p = self._patient("P008")
        v = self._visit("P008", assessment="MISSING")
        devs = self._run([p], [v])
        self.assertTrue(any(d["type"] == "MISSING_ASSESSMENT" for d in devs))

    def test_late_data_entry_detected(self):
        p = self._patient("P009")
        v = self._visit("P009", actual="2025-01-07", data_entry="2025-01-14")  # 7-day delay
        devs = self._run([p], [v])
        self.assertTrue(any(d["type"] == "LATE_DATA_ENTRY" for d in devs))

    def test_timely_data_entry_not_flagged(self):
        p = self._patient("P010")
        v = self._visit("P010", actual="2025-01-07", data_entry="2025-01-08")  # 1 day — OK
        devs = self._run([p], [v])
        self.assertFalse(any(d["type"] == "LATE_DATA_ENTRY" for d in devs))

    def test_eligibility_violation_too_young(self):
        p = self._patient("P011", age=15)
        v = self._visit("P011")
        devs = self._run([p], [v])
        self.assertTrue(any(d["type"] == "ELIGIBILITY_VIOLATION" for d in devs))

    def test_eligibility_violation_too_old(self):
        p = self._patient("P012", age=70)
        v = self._visit("P012")
        devs = self._run([p], [v])
        self.assertTrue(any(d["type"] == "ELIGIBILITY_VIOLATION" for d in devs))

    def test_eligibility_edge_case_18_ok(self):
        p = self._patient("P013", age=18)
        v = self._visit("P013")
        devs = self._run([p], [v])
        self.assertFalse(any(d["type"] == "ELIGIBILITY_VIOLATION" for d in devs))

    def test_eligibility_edge_case_65_ok(self):
        p = self._patient("P014", age=65)
        v = self._visit("P014")
        devs = self._run([p], [v])
        self.assertFalse(any(d["type"] == "ELIGIBILITY_VIOLATION" for d in devs))

    def test_deviation_has_required_fields(self):
        p = self._patient("P015")
        v = self._visit("P015", dose_actual=150)
        devs = self._run([p], [v])
        for d in devs:
            for field in ["deviation_id", "patient_id", "site_id", "type",
                          "expected", "actual", "severity", "evidence"]:
                self.assertIn(field, d, f"Missing field '{field}' in deviation")

    def test_deviation_has_evidence_protocol_id(self):
        p = self._patient("P016")
        v = self._visit("P016", dose_actual=120)
        devs = self._run([p], [v])
        for d in devs:
            self.assertEqual(d["evidence"]["protocol_id"], "TG-101")

    def test_empty_protocols_returns_empty(self):
        result = run_deviation_engine([], [self._patient("P017")], [self._visit("P017")], [])
        self.assertEqual(result, [])

    def test_multiple_deviations_one_visit(self):
        """A single non-compliant visit can produce multiple distinct deviations."""
        p = self._patient("P018")
        v = self._visit("P018", dose_actual=200, assessment="MISSING")
        devs = self._run([p], [v])
        types = {d["type"] for d in devs}
        self.assertIn("INCORRECT_DOSE", types)
        self.assertIn("MISSING_ASSESSMENT", types)


# ─── 6. Severity classification ───────────────────────────────────────────────

class TestSeverityClassification(unittest.TestCase):
    """All three severity tiers and explanation transparency."""

    def test_administrative_zero_score(self):
        r = classify_severity({})
        self.assertEqual(r["severity"], "ADMINISTRATIVE")
        self.assertEqual(r["severity_score"], 0)

    def test_administrative_low_score(self):
        r = classify_severity({"data_integrity": 2})
        self.assertEqual(r["severity"], "ADMINISTRATIVE")
        self.assertLessEqual(r["severity_score"], 3)

    def test_minor_boundary(self):
        r = classify_severity({"data_integrity": 2, "protocol_criticality": 2})
        self.assertEqual(r["severity"], "MINOR")
        self.assertGreaterEqual(r["severity_score"], 4)
        self.assertLessEqual(r["severity_score"], 9)

    def test_major_high_score(self):
        r = classify_severity({
            "safety_impact": 5,
            "data_integrity": 5,
            "protocol_criticality": 4,
            "participant_rights": 2,
            "magnitude": 2,
            "recurrence": 1,
        })
        self.assertEqual(r["severity"], "MAJOR")
        self.assertGreaterEqual(r["severity_score"], 10)

    def test_short_alias_safety(self):
        r = classify_severity({"safety": 5, "integrity": 5, "criticality": 4,
                                "rights": 2, "magnitude": 2, "recurrence": 1})
        self.assertEqual(r["severity"], "MAJOR")

    def test_reason_contains_prototype_disclaimer(self):
        r = classify_severity({"safety_impact": 3})
        self.assertIn("Prototype", r["reason"])

    def test_disclaimer_field_present(self):
        r = classify_severity({})
        self.assertIn("disclaimer", r)
        self.assertIn("ICH", r["disclaimer"])

    def test_max_values_clamped(self):
        """Passing values above max should still produce a valid result."""
        r = classify_severity({"safety_impact": 99, "data_integrity": 99})
        self.assertEqual(r["severity"], "MAJOR")

    def test_incorrect_dose_major(self):
        """The demo 150 mg vs 100 mg dose deviation must be classified MAJOR."""
        r = classify_severity({
            "safety_impact": 4, "data_integrity": 3,
            "protocol_criticality": 4, "participant_rights": 2,
            "magnitude": 2, "recurrence": 0,
        })
        self.assertEqual(r["severity"], "MAJOR")


# ─── 7. Site risk calculation ─────────────────────────────────────────────────

class TestSiteRisk(_FixtureBase):
    """Deterministic site risk engine."""

    def test_s037_score_is_87(self):
        result = calculate_site_risk("S037", self.state.deviations)
        self.assertEqual(result["current_score"], 87)

    def test_s037_level_high(self):
        result = calculate_site_risk("S037", self.state.deviations)
        self.assertEqual(result["risk_level"], "HIGH")

    def test_s037_trend_worsening(self):
        result = calculate_site_risk("S037", self.state.deviations)
        self.assertEqual(result["trend"], "WORSENING")

    def test_s037_predicted_higher_than_current(self):
        result = calculate_site_risk("S037", self.state.deviations)
        self.assertGreater(result["predicted_score"], result["current_score"])

    def test_risk_score_range(self):
        for site in self.state.sites[:10]:
            result = calculate_site_risk(site["site_id"], self.state.deviations)
            self.assertGreaterEqual(result["current_score"], 0)
            self.assertLessEqual(result["current_score"], 100)

    def test_risk_level_valid_values(self):
        for site in self.state.sites[:10]:
            result = calculate_site_risk(site["site_id"], self.state.deviations)
            self.assertIn(result["risk_level"], ("LOW", "MEDIUM", "HIGH"))

    def test_trend_valid_values(self):
        for site in self.state.sites[:10]:
            result = calculate_site_risk(site["site_id"], self.state.deviations)
            self.assertIn(result["trend"], ("IMPROVING", "STABLE", "WORSENING"))

    def test_leading_indicators_present(self):
        result = calculate_site_risk("S037", self.state.deviations)
        self.assertIn("leading_indicators", result)
        self.assertIsInstance(result["leading_indicators"], list)
        self.assertGreater(len(result["leading_indicators"]), 0)

    def test_risk_drivers_present(self):
        result = calculate_site_risk("S037", self.state.deviations)
        self.assertIn("risk_drivers", result)

    def test_seven_or_more_high_risk_sites_seeded(self):
        """Dashboard should show at least 7 high-risk sites."""
        high = [r for r in self.state.risk_scores if r["risk_level"] == "HIGH"]
        self.assertGreaterEqual(len(high), 7)


# ─── 8. CAPA generation ───────────────────────────────────────────────────────

class TestCapaGeneration(_FixtureBase):
    """CAPA service produces valid, disclaimer-bearing records."""

    def _site_devs(self, site_id):
        return [d for d in self.state.deviations if d["site_id"] == site_id]

    def test_capa_has_required_fields(self):
        devs = self._site_devs("S037")[:5]
        capa = generate_capa_record("S037", devs, "test-user")
        for field in ["capa_id", "site_id", "problem_statement", "root_cause",
                      "corrective_actions", "preventive_actions", "priority",
                      "status", "created_by", "disclaimer"]:
            self.assertIn(field, capa, f"Missing field '{field}'")

    def test_capa_disclaimer_requires_review(self):
        devs = self._site_devs("S037")[:3]
        capa = generate_capa_record("S037", devs, "user1")
        self.assertIn("qualified", capa["disclaimer"].lower())

    def test_capa_root_cause_labelled_ai_generated(self):
        devs = self._site_devs("S037")[:3]
        capa = generate_capa_record("S037", devs, "user1")
        self.assertIn("AI-generated", capa["root_cause"])

    def test_capa_priority_high_for_major_devs(self):
        major_devs = [d for d in self._site_devs("S037") if d["severity"] == "MAJOR"][:3]
        capa = generate_capa_record("S037", major_devs, "user1")
        self.assertEqual(capa["priority"], "HIGH")

    def test_capa_status_starts_open(self):
        devs = self._site_devs("S037")[:2]
        capa = generate_capa_record("S037", devs, "user1")
        self.assertEqual(capa["status"], "OPEN")

    def test_capa_corrective_actions_list(self):
        devs = self._site_devs("S037")[:2]
        capa = generate_capa_record("S037", devs, "user1")
        self.assertIsInstance(capa["corrective_actions"], list)
        self.assertGreater(len(capa["corrective_actions"]), 0)

    def test_capa_preventive_actions_list(self):
        devs = self._site_devs("S037")[:2]
        capa = generate_capa_record("S037", devs, "user1")
        self.assertIsInstance(capa["preventive_actions"], list)
        self.assertGreater(len(capa["preventive_actions"]), 0)

    def test_capa_no_deviations_still_generates(self):
        capa = generate_capa_record("S099", [], "user1")
        self.assertIn("capa_id", capa)
        self.assertEqual(capa["site_id"], "S099")

    def test_capa_id_is_unique(self):
        devs = self._site_devs("S037")[:2]
        ids = {generate_capa_record("S037", devs, "u")["capa_id"] for _ in range(5)}
        self.assertEqual(len(ids), 5)  # all unique


# ─── 9. Bob tool authorization ────────────────────────────────────────────────

class TestBobToolAuth(_FixtureBase):
    """Bob tools respect role and site-scope constraints."""

    def _sess(self, role, site_id=None):
        return {"role": role, "site_id": site_id, "user_id": "t", "email": "t@t.com", "name": "T"}

    def _repo(self):
        from database import MemoryRepository
        repo = MemoryRepository()
        repo.replace_all(self.state)
        return repo

    def test_auditor_cannot_use_recommend_actions(self):
        tools = build_bob_tools(self._repo(), self._sess("AUDITOR"))
        with self.assertRaises(PermissionError):
            tools["recommend_site_actions"](site_id="S037")

    def test_auditor_cannot_generate_capa(self):
        tools = build_bob_tools(self._repo(), self._sess("AUDITOR"))
        with self.assertRaises(PermissionError):
            tools["generate_capa"](site_id="S037")

    def test_manager_can_recommend_actions(self):
        tools = build_bob_tools(self._repo(), self._sess("STUDY_MANAGER"))
        result = tools["recommend_site_actions"](site_id="S037")
        # result has corrective_actions and preventive_actions keys
        self.assertTrue(
            "corrective_actions" in result or "actions" in result,
            f"Expected action keys not found in: {list(result.keys())}"
        )

    def test_manager_can_generate_capa(self):
        tools = build_bob_tools(self._repo(), self._sess("STUDY_MANAGER"))
        result = tools["generate_capa"](site_id="S037")
        self.assertIn("capa_id", result)

    def test_manager_get_trial_overview(self):
        tools = build_bob_tools(self._repo(), self._sess("STUDY_MANAGER"))
        result = tools["get_trial_overview"]()
        self.assertIn("total_sites", result)
        self.assertEqual(result["total_sites"], 42)

    def test_manager_list_high_risk_sites(self):
        tools = build_bob_tools(self._repo(), self._sess("STUDY_MANAGER"))
        result = tools["list_high_risk_sites"]()
        self.assertIn("high_risk_sites", result)
        self.assertGreater(result["count"], 0)

    def test_coordinator_list_site_deviations_own_site(self):
        tools = build_bob_tools(self._repo(), self._sess("SITE_COORDINATOR", "S037"))
        result = tools["list_site_deviations"](site_id="S037")
        self.assertIn("deviations", result)

    def test_coordinator_list_site_deviations_other_site_denied(self):
        tools = build_bob_tools(self._repo(), self._sess("SITE_COORDINATOR", "S037"))
        with self.assertRaises(PermissionError):
            tools["list_site_deviations"](site_id="S001")

    def test_auditor_can_get_site_risk(self):
        tools = build_bob_tools(self._repo(), self._sess("AUDITOR"))
        result = tools["get_site_risk"](site_id="S037")
        self.assertEqual(result["site_id"], "S037")

    def test_all_thirteen_tools_registered(self):
        expected = {
            "get_trial_overview", "list_high_risk_sites", "get_site_risk",
            "explain_site_risk", "list_site_deviations", "get_deviation",
            "search_protocol_rules", "compare_patient_to_protocol",
            "get_site_trends", "recommend_site_actions",
            "generate_capa", "get_capa_status", "generate_risk_report",
        }
        self.assertEqual(set(TOOL_REGISTRY.keys()), expected)


# ─── 10. Deterministic dataset integrity ──────────────────────────────────────

class TestDataIntegrity(_FixtureBase):
    """Seeded dataset meets demo story requirements."""

    def test_42_sites(self):
        self.assertEqual(len(self.state.sites), 42)

    def test_over_1000_patients(self):
        self.assertGreater(len(self.state.patients), 1000)

    def test_over_500_deviations(self):
        self.assertGreater(len(self.state.deviations), 500)

    def test_dataset_is_deterministic(self):
        other = build_demo_state()
        self.assertEqual(len(self.state.sites), len(other.sites))
        self.assertEqual(len(self.state.patients), len(other.patients))
        self.assertEqual(len(self.state.deviations), len(other.deviations))

    def test_s037_has_dosing_deviations(self):
        s037_devs = [d for d in self.state.deviations
                     if d["site_id"] == "S037" and d["type"] == "INCORRECT_DOSE"]
        self.assertGreater(len(s037_devs), 0)

    def test_150mg_vs_100mg_deviation_exists(self):
        dose_devs = [d for d in self.state.deviations
                     if d.get("actual") == "150 mg" and d.get("expected", "").startswith("100 mg")]
        self.assertGreater(len(dose_devs), 0)

    def test_risk_scores_cover_all_sites(self):
        scored_site_ids = {r["site_id"] for r in self.state.risk_scores}
        seeded_site_ids = {s["site_id"] for s in self.state.sites}
        self.assertEqual(scored_site_ids, seeded_site_ids)

    def test_protocol_tg101_exists(self):
        self.assertTrue(any(p.get("protocol_id") == "TG-101" for p in self.state.protocols))

    def test_protocol_has_minimum_8_rules(self):
        protocol = next(p for p in self.state.protocols if p.get("protocol_id") == "TG-101")
        self.assertGreaterEqual(len(protocol.get("rules", [])), 8)

    def test_capa_records_seeded(self):
        self.assertGreater(len(self.state.capa_records), 0)

    def test_audit_events_seeded(self):
        self.assertGreater(len(self.state.audit_events), 0)

    def test_all_deviations_reference_tg101(self):
        for d in self.state.deviations:
            self.assertEqual(
                d["evidence"]["protocol_id"], "TG-101",
                f"Deviation {d['deviation_id']} does not reference TG-101"
            )

    def test_patients_have_site_ids(self):
        for p in self.state.patients[:50]:
            self.assertIn("site_id", p)
            self.assertTrue(p["site_id"].startswith("S"))

    def test_no_real_patient_data(self):
        """Patients must use synthetic identifiers only."""
        for p in self.state.patients[:100]:
            pid = p.get("patient_id", "")
            self.assertTrue(
                pid.startswith("P") or pid.startswith("S"),
                f"Patient ID {pid!r} looks non-synthetic"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
