"""
TrialGuard AI — LocalDemoBobProvider Intent Routing Tests

Verifies:
1. Non-TrialGuard messages (greetings, jokes, weather) → UNSUPPORTED (tool_used=None)
2. TrialGuard-specific messages → correct tool
3. No hardcoded S037 default
4. RBAC enforcement through the provider

These tests cover the 10 required cases from the spec plus additional coverage.

Run with:
    cd src && python tests/test_routing.py
"""
from __future__ import annotations

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import User
from database import MemoryRepository
from bob_boundary import LocalDemoBobProvider, build_bob_tools
from synthetic_data import build_demo_state


def _make_repo():
    repo = MemoryRepository()
    repo.replace_all(build_demo_state())
    return repo


def _user(role="STUDY_MANAGER", site_id=None):
    return User(
        user_id=f"test-{role.lower()}",
        name="Test User",
        email=f"test@{role.lower()}.demo",
        password_hash="",
        role=role,
        site_id=site_id,
    )


class TestIntentRouting(unittest.TestCase):
    """The 10 required routing test cases + additional coverage."""

    @classmethod
    def setUpClass(cls):
        cls.repo = _make_repo()
        cls.sess = {"role": "STUDY_MANAGER", "user_id": "test", "site_id": None}
        cls.tools = build_bob_tools(cls.repo, cls.sess)
        cls.provider = LocalDemoBobProvider()
        cls.mgr = _user("STUDY_MANAGER")

    def _ask(self, question):
        return self.provider.answer(question, self.mgr, self.tools)

    def _tool(self, question):
        return self._ask(question).get("tool_used")

    # ── TEST 1: hello → NONE ──────────────────────────────────────────────────
    def test_01_hello_is_unsupported(self):
        result = self._ask("hello")
        self.assertIsNone(result.get("tool_used"), "hello must not call any tool")
        self.assertIn("TrialGuard", result["answer"])

    # ── TEST 2: hi → NONE ────────────────────────────────────────────────────
    def test_02_hi_is_unsupported(self):
        result = self._ask("hi")
        self.assertIsNone(result.get("tool_used"), "hi must not call any tool")

    # ── TEST 3: Why is S037 high risk? → explain_site_risk ───────────────────
    def test_03_why_s037_high_risk(self):
        self.assertEqual(self._tool("Why is Site S037 high risk?"), "explain_site_risk")

    # ── TEST 4: Which sites are high risk? → list_high_risk_sites ────────────
    def test_04_which_sites_high_risk(self):
        self.assertEqual(self._tool("Which sites are high risk?"), "list_high_risk_sites")

    # ── TEST 5: Show me deviations at S037 → list_site_deviations ────────────
    def test_05_show_deviations_s037(self):
        self.assertEqual(self._tool("Show me the deviations at S037."), "list_site_deviations")

    # ── TEST 6: Show trend for S037 → get_site_trends ────────────────────────
    def test_06_show_trend_s037(self):
        self.assertEqual(self._tool("Show me the trend for S037."), "get_site_trends")

    # ── TEST 7: Generate CAPA for S037 → generate_capa ───────────────────────
    def test_07_generate_capa_s037(self):
        self.assertEqual(self._tool("Generate a CAPA for S037."), "generate_capa")

    # ── TEST 8: Tell me a joke → NONE ────────────────────────────────────────
    def test_08_tell_me_a_joke_is_unsupported(self):
        self.assertIsNone(self._tool("Tell me a joke."))

    # ── TEST 9: Weather → NONE ───────────────────────────────────────────────
    def test_09_weather_is_unsupported(self):
        self.assertIsNone(self._tool("What is the weather today?"))

    # ── TEST 10: Overview of clinical trial → get_trial_overview ─────────────
    def test_10_trial_overview(self):
        self.assertEqual(self._tool("Give me an overview of the clinical trial."), "get_trial_overview")

    # ── Additional non-TrialGuard inputs ─────────────────────────────────────
    def test_good_morning_is_unsupported(self):
        self.assertIsNone(self._tool("good morning"))

    def test_how_are_you_is_unsupported(self):
        self.assertIsNone(self._tool("how are you"))

    def test_thanks_is_unsupported(self):
        self.assertIsNone(self._tool("thanks"))

    def test_random_text_is_unsupported(self):
        self.assertIsNone(self._tool("random text"))

    def test_empty_ish_question_is_unsupported(self):
        self.assertIsNone(self._tool("what"))

    # ── Additional TrialGuard routing ─────────────────────────────────────────
    def test_worsening_trend_s037(self):
        self.assertEqual(self._tool("Is S037's risk getting worse?"), "get_site_trends")

    def test_recommend_actions_s037(self):
        self.assertEqual(self._tool("What actions are recommended for S037?"), "recommend_site_actions")

    def test_site_summary_routes_to_overview(self):
        self.assertEqual(self._tool("Give me a summary of the trial"), "get_trial_overview")

    def test_highest_risk_sites(self):
        result = self._tool("Which sites have the highest risk?")
        self.assertEqual(result, "list_high_risk_sites")

    def test_generate_risk_report(self):
        self.assertEqual(self._tool("Generate a risk report for S037"), "generate_risk_report")


class TestNoHardcodedS037Default(unittest.TestCase):
    """Verify S037 is never used as a default site for unrelated messages."""

    @classmethod
    def setUpClass(cls):
        cls.repo = _make_repo()
        cls.sess = {"role": "STUDY_MANAGER", "user_id": "test", "site_id": None}
        cls.tools = build_bob_tools(cls.repo, cls.sess)
        cls.provider = LocalDemoBobProvider()
        cls.mgr = _user("STUDY_MANAGER")

    def _ask(self, question):
        return self.provider.answer(question, self.mgr, self.tools)

    def _answer_contains_s037_risk_data(self, result):
        """Returns True if the answer contains actual S037 risk score data."""
        answer = result.get("answer", "")
        # Check for specific S037 risk data, not just the site name in a suggestion
        return "87/100" in answer or ("S037" in answer and "risk score" in answer.lower())

    def test_hello_does_not_return_s037_risk_data(self):
        result = self._ask("hello")
        self.assertFalse(
            self._answer_contains_s037_risk_data(result),
            f"'hello' must NOT return S037 risk data. Got: {result['answer'][:200]}"
        )

    def test_hi_does_not_return_s037_risk_data(self):
        result = self._ask("hi")
        self.assertFalse(
            self._answer_contains_s037_risk_data(result),
            f"'hi' must NOT return S037 risk data. Got: {result['answer'][:200]}"
        )

    def test_joke_does_not_return_s037_risk_data(self):
        result = self._ask("Tell me a joke")
        self.assertFalse(self._answer_contains_s037_risk_data(result))

    def test_weather_does_not_return_s037_risk_data(self):
        result = self._ask("What is the weather?")
        self.assertFalse(self._answer_contains_s037_risk_data(result))

    def test_s037_mention_in_clinical_context_does_use_s037(self):
        """When S037 is explicitly mentioned in a clinical context, it IS used."""
        result = self._ask("Why is Site S037 high risk?")
        self.assertEqual(result.get("tool_used"), "explain_site_risk")
        self.assertIn("87", result.get("answer", ""))

    def test_tool_used_is_none_for_unsupported(self):
        """tool_used field is None for unsupported messages."""
        for msg in ["hello", "hi", "bye", "thanks", "Tell me a joke"]:
            result = self._ask(msg)
            self.assertIsNone(
                result.get("tool_used"),
                f"tool_used should be None for '{msg}', got {result.get('tool_used')!r}"
            )

    def test_unsupported_response_mentions_trialguard(self):
        """Unsupported responses guide the user to TrialGuard questions."""
        result = self._ask("hello")
        self.assertIn("TrialGuard", result["answer"])

    def test_no_hardcoded_s037_in_site_scoped_response_without_site(self):
        """A TrialGuard-scoped question without a site asks for the site ID, not S037."""
        result = self._ask("Why is the site high risk?")
        # If no site ID is in the message and user has no site_id, should ask for site ID
        answer = result.get("answer", "")
        # Must NOT contain S037 risk data
        self.assertFalse(
            self._answer_contains_s037_risk_data(result),
            f"Should not default to S037 data. Got: {answer[:200]}"
        )


class TestRBACThroughProvider(unittest.TestCase):
    """RBAC enforcement tests through LocalDemoBobProvider."""

    @classmethod
    def setUpClass(cls):
        cls.repo = _make_repo()

    def _provider_answer(self, question, role, site_id=None):
        sess = {"role": role, "user_id": f"test-{role}", "site_id": site_id}
        tools = build_bob_tools(self.repo, sess)
        provider = LocalDemoBobProvider()
        user = _user(role, site_id)
        return provider.answer(question, user, tools)

    def test_auditor_cannot_generate_capa(self):
        result = self._provider_answer("Generate a CAPA for S037", "AUDITOR")
        # Should either be redirected to explain_site_risk or return unsupported
        tool = result.get("tool_used")
        self.assertNotEqual(tool, "generate_capa", "AUDITOR must not call generate_capa")

    def test_study_manager_can_generate_capa(self):
        result = self._provider_answer("Generate a CAPA for S037", "STUDY_MANAGER")
        self.assertEqual(result.get("tool_used"), "generate_capa")

    def test_coordinator_cross_site_denied(self):
        result = self._provider_answer("Why is Site S008 high risk?", "SITE_COORDINATOR", site_id="S037")
        self.assertIn("permission", result["answer"].lower())

    def test_coordinator_own_site_allowed(self):
        result = self._provider_answer("Why is Site S037 high risk?", "SITE_COORDINATOR", site_id="S037")
        self.assertIn("tool_used", result)
        self.assertNotIn("permission", result["answer"].lower())


class TestProviderBadge(unittest.TestCase):
    """Verify the provider name badge is clear about what it is."""

    def test_provider_name_says_not_ibm_bob(self):
        p = LocalDemoBobProvider()
        self.assertIn("not IBM Bob", p.name)
        self.assertIn("DEMO", p.name)

    def test_provider_name_in_every_response(self):
        repo = _make_repo()
        sess = {"role": "STUDY_MANAGER", "user_id": "test", "site_id": None}
        tools = build_bob_tools(repo, sess)
        provider = LocalDemoBobProvider()
        mgr = _user("STUDY_MANAGER")

        for question in ["hello", "Why is Site S037 high risk?", "Which sites are high risk?"]:
            result = provider.answer(question, mgr, tools)
            self.assertEqual(result["provider"], provider.name)


class TestCompareSites(unittest.TestCase):
    """Tests for the COMPARE_SITES shortcut and _handle_compare/_compose_compare."""

    @classmethod
    def setUpClass(cls):
        cls.repo = _make_repo()
        cls.sess = {"role": "STUDY_MANAGER", "user_id": "test", "site_id": None}
        cls.tools = build_bob_tools(cls.repo, cls.sess)
        cls.provider = LocalDemoBobProvider()
        cls.mgr = _user("STUDY_MANAGER")

    def _ask(self, question):
        return self.provider.answer(question, self.mgr, self.tools)

    def _tool(self, question):
        return self._ask(question).get("tool_used")

    # ── COMPARE_SITES triggers ────────────────────────────────────────────
    def test_compare_two_sites_standard(self):
        result = self._ask("generate comparison report of S001 vs S032")
        self.assertEqual(result.get("tool_used"), "compare_sites")

    def test_compare_two_sites_versus(self):
        result = self._ask("compare S001 versus S032")
        self.assertEqual(result.get("tool_used"), "compare_sites")

    def test_compare_two_sites_and(self):
        result = self._ask("compare sites S001 and S032")
        self.assertEqual(result.get("tool_used"), "compare_sites")

    def test_compare_answer_contains_both_site_ids(self):
        result = self._ask("compare S001 and S032")
        answer = result.get("answer", "")
        self.assertIn("S001", answer)
        self.assertIn("S032", answer)

    def test_compare_answer_contains_risk_score(self):
        result = self._ask("compare S001 and S032")
        answer = result.get("answer", "")
        self.assertIn("Risk score", answer)

    def test_compare_answer_contains_verdict(self):
        result = self._ask("compare S001 and S032")
        answer = result.get("answer", "")
        self.assertIn("Verdict", answer)

    def test_compare_answer_contains_separator(self):
        result = self._ask("compare S001 and S032")
        answer = result.get("answer", "")
        # Should have ASCII separator lines, not Unicode box-drawing chars
        self.assertIn("---", answer)
        self.assertNotIn("\u2500", answer)  # box-drawing ─
        self.assertNotIn("\u2014", answer)  # em-dash —

    def test_compare_single_site_does_not_trigger_compare(self):
        """A message with only one site ID should NOT trigger compare_sites."""
        result = self._ask("What is the risk at S037?")
        self.assertNotEqual(result.get("tool_used"), "compare_sites")

    def test_compare_no_site_does_not_trigger_compare(self):
        """A message with no site IDs should NOT trigger compare_sites."""
        result = self._ask("compare all sites")
        self.assertNotEqual(result.get("tool_used"), "compare_sites")

    def test_compare_returns_provider_badge(self):
        result = self._ask("compare S001 and S032")
        self.assertEqual(result.get("provider"), self.provider.name)

    def test_coordinator_cross_site_compare_denied(self):
        """SITE_COORDINATOR cannot compare two sites if one is not theirs."""
        sess = {"role": "SITE_COORDINATOR", "user_id": "coord", "site_id": "S001"}
        tools = build_bob_tools(self.repo, sess)
        coord = _user("SITE_COORDINATOR", site_id="S001")
        result = self.provider.answer("compare S001 and S032", coord, tools)
        # Cross-site: S032 != S001 — should be blocked by RBAC
        self.assertIn("permission", result["answer"].lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
