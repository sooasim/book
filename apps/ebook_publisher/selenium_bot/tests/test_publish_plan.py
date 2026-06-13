"""publish_plan 모듈 단위 테스트(표준 라이브러리 unittest)."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from selenium_bot.models import HUMAN_GATES, PlanStep, PlatformSite, PublishPlan
from selenium_bot.publish_plan import (
    assert_plan_invariants,
    auto_steps,
    build_publish_plan,
    human_steps,
    plan_to_dict,
    plan_to_json,
)


def _fake_site(gates=None):
    return PlatformSite(
        platform_id="fakeplat",
        region="global",
        platform_name="Fake Platform",
        entry_type="self_publish",
        primary_url="https://example.com/publish",
        signup_url="https://example.com/signup",
        human_gates=list(gates) if gates is not None else ["captcha", "tax_info", "final_submit"],
    )


def _fake_book():
    return {
        "book_id": "bk-001",
        "title": "나의 첫 책",
        "subtitle": "부제목",
        "author": "홍길동",
        "description": "이 책에 대한 설명입니다.",
        "keywords": ["소설", "판타지"],
        "categories": ["Fiction"],
        "price_usd": "9.99",
        "price_krw": "12000",
        "language": "ko",
        "isbn_ebook": "978-0-00-000000-0",
    }


class TestBuildPublishPlan(unittest.TestCase):
    def setUp(self):
        self.site = _fake_site(["captcha", "tax_info", "final_submit"])
        self.book = _fake_book()
        self.files = {"epub": "/tmp/book.epub", "cover": "/tmp/cover.png"}
        self.plan = build_publish_plan(self.book, self.site, self.files)

    def test_returns_publish_plan(self):
        self.assertIsInstance(self.plan, PublishPlan)
        self.assertEqual(self.plan.platform_id, "fakeplat")
        self.assertEqual(self.plan.book_id, "bk-001")
        self.assertTrue(self.plan.created_at)

    def test_first_step_open_url(self):
        first = self.plan.steps[0]
        self.assertEqual(first.action, "open_url")
        self.assertEqual(first.value, "https://example.com/publish")

    def test_second_step_wait_human_login(self):
        second = self.plan.steps[1]
        self.assertEqual(second.action, "wait_human_login")
        self.assertTrue(second.human)

    def test_fill_steps_contain_title_and_description(self):
        fills = {s.field_key: s.value for s in self.plan.steps if s.action == "fill"}
        self.assertIn("title", fills)
        self.assertEqual(fills["title"], "나의 첫 책")
        self.assertIn("description", fills)

    def test_keywords_list_joined(self):
        fills = {s.field_key: s.value for s in self.plan.steps if s.action == "fill"}
        self.assertEqual(fills["keywords"], "소설, 판타지")

    def test_upload_step_present(self):
        uploads = [s for s in self.plan.steps if s.action == "upload"]
        keys = {s.field_key for s in uploads}
        self.assertIn("manuscript_file", keys)
        self.assertIn("cover_file", keys)
        manuscript = next(s for s in uploads if s.field_key == "manuscript_file")
        self.assertEqual(manuscript.value, "/tmp/book.epub")

    def test_price_prefers_usd(self):
        prices = [s for s in self.plan.steps if s.field_key == "price"]
        self.assertEqual(len(prices), 1)
        self.assertEqual(prices[0].value, "9.99")

    def test_price_falls_back_to_krw(self):
        book = _fake_book()
        del book["price_usd"]
        plan = build_publish_plan(book, self.site)
        prices = [s for s in plan.steps if s.field_key == "price"]
        self.assertEqual(prices[0].value, "12000")

    def test_last_step_is_final_submit(self):
        last = self.plan.steps[-1]
        self.assertEqual(last.action, "human_gate")
        self.assertEqual(last.gate, "final_submit")
        self.assertTrue(last.human)

    def test_final_submit_always_last_even_if_not_in_site_gates(self):
        site = _fake_site(["captcha", "tax_info"])  # no final_submit
        plan = build_publish_plan(self.book, site, self.files)
        self.assertEqual(plan.steps[-1].gate, "final_submit")
        # exactly one final_submit
        finals = [s for s in plan.steps if s.gate == "final_submit"]
        self.assertEqual(len(finals), 1)

    def test_no_duplicate_final_submit_when_in_site_gates(self):
        finals = [s for s in self.plan.steps if s.gate == "final_submit"]
        self.assertEqual(len(finals), 1)

    def test_site_gates_become_human_gates(self):
        gates = [s.gate for s in self.plan.steps if s.action == "human_gate"]
        self.assertIn("captcha", gates)
        self.assertIn("tax_info", gates)

    def test_no_files_means_no_uploads(self):
        plan = build_publish_plan(self.book, self.site)
        uploads = [s for s in plan.steps if s.action == "upload"]
        self.assertEqual(uploads, [])

    def test_manuscript_key_also_accepted(self):
        plan = build_publish_plan(self.book, self.site, {"manuscript": "/tmp/m.docx"})
        uploads = [s for s in plan.steps if s.field_key == "manuscript_file"]
        self.assertEqual(uploads[0].value, "/tmp/m.docx")

    def test_missing_metadata_fields_skipped(self):
        book = {"book_id": "x", "title": "only title"}
        plan = build_publish_plan(book, self.site)
        fills = {s.field_key for s in plan.steps if s.action == "fill"}
        self.assertEqual(fills, {"title"})


class TestFiltersAndInvariants(unittest.TestCase):
    def setUp(self):
        self.plan = build_publish_plan(_fake_book(), _fake_site(), {"epub": "/tmp/b.epub"})

    def test_auto_steps_have_no_human_gates(self):
        for step in auto_steps(self.plan):
            self.assertNotEqual(step.action, "human_gate")
            self.assertEqual(step.gate, "")

    def test_human_steps_include_gates(self):
        gates = [s for s in human_steps(self.plan) if s.action == "human_gate"]
        self.assertTrue(gates)

    def test_every_human_gate_in_contract(self):
        for step in self.plan.steps:
            if step.action == "human_gate":
                self.assertIn(step.gate, HUMAN_GATES)
                self.assertTrue(step.human)

    def test_no_automatable_step_carries_gate(self):
        for step in self.plan.steps:
            if step.action != "human_gate":
                self.assertEqual(step.gate, "")

    def test_invariants_pass(self):
        assert_plan_invariants(self.plan)  # should not raise

    def test_invariants_detect_bad_gate(self):
        bad = build_publish_plan(_fake_book(), _fake_site())
        bad.steps.append(PlanStep(action="human_gate", gate="not_a_real_gate", human=True))
        with self.assertRaises(ValueError):
            assert_plan_invariants(bad)


class TestSerialization(unittest.TestCase):
    def setUp(self):
        self.plan = build_publish_plan(_fake_book(), _fake_site(), {"epub": "/tmp/b.epub"})

    def test_plan_to_dict(self):
        d = plan_to_dict(self.plan)
        self.assertIsInstance(d, dict)
        self.assertEqual(d["platform_id"], "fakeplat")
        self.assertIsInstance(d["steps"], list)
        self.assertIsInstance(d["steps"][0], dict)

    def test_plan_to_json_roundtrips(self):
        text = plan_to_json(self.plan)
        loaded = json.loads(text)
        self.assertEqual(loaded["platform_id"], "fakeplat")
        self.assertEqual(loaded["book_id"], "bk-001")
        self.assertEqual(loaded["steps"][-1]["gate"], "final_submit")

    def test_json_has_no_password_field(self):
        text = plan_to_json(self.plan)
        self.assertNotIn("password", text)


class TestDeterminism(unittest.TestCase):
    def test_step_structure_deterministic(self):
        book = _fake_book()
        site = _fake_site()
        files = {"epub": "/tmp/b.epub", "cover": "/tmp/c.png"}
        a = build_publish_plan(book, site, files)
        b = build_publish_plan(book, site, files)
        # created_at may differ; compare everything else.
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
