"""account_prep 모듈 단위 테스트(표준 라이브러리 unittest)."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from selenium_bot.models import HUMAN_GATES, PlatformSite, PublishPlan, SignupProfile
from selenium_bot.account_prep import build_signup_plan, signup_human_gates

_FORBIDDEN = {"password", "tax", "payout", "ssn", "card"}


def _fake_site(gates=None):
    return PlatformSite(
        platform_id="fakeplat",
        region="global",
        platform_name="Fake Platform",
        entry_type="self_publish",
        primary_url="https://example.com/home",
        signup_url="https://example.com/signup",
        human_gates=list(gates) if gates is not None else [
            "captcha",
            "email_verify",
            "tos_agree",
            "tax_info",
            "final_submit",
        ],
    )


def _fake_profile():
    return SignupProfile(
        platform_id="fakeplat",
        display_name="길동",
        email="hong@example.com",
        pen_name="필명홍",
        country="KR",
    )


class TestBuildSignupPlan(unittest.TestCase):
    def setUp(self):
        self.site = _fake_site()
        self.profile = _fake_profile()
        self.plan = build_signup_plan(self.profile, self.site)

    def test_returns_publish_plan_with_empty_book_id(self):
        self.assertIsInstance(self.plan, PublishPlan)
        self.assertEqual(self.plan.book_id, "")
        self.assertEqual(self.plan.platform_id, "fakeplat")
        self.assertTrue(self.plan.created_at)

    def test_first_step_open_signup_url(self):
        first = self.plan.steps[0]
        self.assertEqual(first.action, "open_url")
        self.assertEqual(first.value, "https://example.com/signup")

    def test_falls_back_to_primary_url(self):
        site = _fake_site()
        site.signup_url = ""
        plan = build_signup_plan(self.profile, site)
        self.assertEqual(plan.steps[0].value, "https://example.com/home")

    def test_fills_email_and_display_name(self):
        fills = {s.field_key: s.value for s in self.plan.steps if s.action == "fill"}
        self.assertEqual(fills.get("email"), "hong@example.com")
        self.assertEqual(fills.get("display_name"), "길동")

    def test_fills_pen_name_and_country(self):
        fills = {s.field_key: s.value for s in self.plan.steps if s.action == "fill"}
        self.assertEqual(fills.get("pen_name"), "필명홍")
        self.assertEqual(fills.get("country"), "KR")

    def test_empty_profile_fields_skipped(self):
        profile = SignupProfile(platform_id="fakeplat", email="x@y.com")
        plan = build_signup_plan(profile, self.site)
        fills = {s.field_key for s in plan.steps if s.action == "fill"}
        self.assertEqual(fills, {"email"})

    def test_never_fills_sensitive_fields(self):
        for step in self.plan.steps:
            self.assertNotIn(step.field_key, _FORBIDDEN)
            self.assertNotEqual(step.field_key, "captcha")

    def test_no_fill_step_clicks_create_account(self):
        # No automatable step should be a create-account submission.
        for step in self.plan.steps:
            if step.action != "human_gate":
                self.assertNotEqual(step.field_key, "captcha")
                self.assertNotIn(step.field_key, _FORBIDDEN)

    def test_account_create_final_present_as_human_gate(self):
        gates = {s.gate for s in self.plan.steps if s.action == "human_gate"}
        self.assertIn("account_create_final", gates)
        final = next(s for s in self.plan.steps if s.gate == "account_create_final")
        self.assertEqual(final.action, "human_gate")
        self.assertTrue(final.human)

    def test_account_create_final_is_last_gate(self):
        gate_steps = [s for s in self.plan.steps if s.action == "human_gate"]
        self.assertEqual(gate_steps[-1].gate, "account_create_final")

    def test_phone_verify_appears_when_required(self):
        site = _fake_site(["captcha", "phone_verify", "final_submit"])
        plan = build_signup_plan(self.profile, site)
        gates = {s.gate for s in plan.steps if s.action == "human_gate"}
        self.assertIn("phone_verify", gates)
        phone = next(s for s in plan.steps if s.gate == "phone_verify")
        self.assertTrue(phone.human)

    def test_no_automatable_step_has_gate(self):
        for step in self.plan.steps:
            if step.action != "human_gate":
                self.assertEqual(step.gate, "")

    def test_every_human_gate_in_contract_and_human(self):
        for step in self.plan.steps:
            if step.action == "human_gate":
                self.assertIn(step.gate, HUMAN_GATES)
                self.assertTrue(step.human)

    def test_no_final_submit_or_publish_gate_in_signup(self):
        # signup plan should not auto-include publishing's final_submit.
        gates = {s.gate for s in self.plan.steps if s.action == "human_gate"}
        self.assertNotIn("final_submit", gates)


class TestSignupHumanGates(unittest.TestCase):
    def test_subset_ordered_with_account_create_final_last(self):
        site = _fake_site(["captcha", "email_verify", "tos_agree", "tax_info", "final_submit"])
        gates = signup_human_gates(site)
        self.assertEqual(gates[-1], "account_create_final")
        # order follows fixed signup order, tax_info/final_submit excluded
        self.assertEqual(gates, ["captcha", "email_verify", "tos_agree", "account_create_final"])

    def test_always_includes_account_create_final_even_if_no_site_gates(self):
        site = _fake_site([])
        gates = signup_human_gates(site)
        self.assertEqual(gates, ["account_create_final"])

    def test_identity_and_phone_included_when_present(self):
        site = _fake_site(["identity_verify", "phone_verify"])
        gates = signup_human_gates(site)
        self.assertIn("phone_verify", gates)
        self.assertIn("identity_verify", gates)
        # phone_verify before identity_verify per fixed order
        self.assertLess(gates.index("phone_verify"), gates.index("identity_verify"))


class TestDeterminism(unittest.TestCase):
    def test_step_structure_deterministic(self):
        profile = _fake_profile()
        site = _fake_site()
        a = build_signup_plan(profile, site)
        b = build_signup_plan(profile, site)
        a_steps = [
            (s.action, s.field_key, s.value, s.gate, s.human, s.note) for s in a.steps
        ]
        b_steps = [
            (s.action, s.field_key, s.value, s.gate, s.human, s.note) for s in b.steps
        ]
        self.assertEqual(a_steps, b_steps)
        self.assertEqual(a.platform_id, b.platform_id)
        self.assertEqual(a.book_id, b.book_id)


if __name__ == "__main__":
    unittest.main()
