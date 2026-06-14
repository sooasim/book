"""어시스턴트 통합 테스트 — 가짜 드라이버로 자동/사람게이트 분기 검증(selenium 불필요).

핵심 안전 단언: 어시스턴트는 human_gate 단계에서 절대 브라우저(find_element/click)를
호출하지 않는다.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from selenium_bot.assistant import SeleniumAssistant  # noqa: E402
from selenium_bot.field_mapping import MappingStore  # noqa: E402
from selenium_bot.models import PlatformSite  # noqa: E402
from selenium_bot.publish_plan import build_publish_plan  # noqa: E402


class FakeElement:
    def __init__(self):
        self.cleared = False
        self.sent = []
        self.clicked = False

    def clear(self):
        self.cleared = True

    def send_keys(self, v):
        self.sent.append(v)

    def click(self):
        self.clicked = True


class FakeDriver:
    """duck-typed selenium driver. 모든 호출을 기록."""
    def __init__(self):
        self.gets = []
        self.find_calls = []
        self._el = FakeElement()

    def get(self, url):
        self.gets.append(url)

    def find_element(self, by, selector):
        self.find_calls.append((by, selector))
        return self._el


def _site():
    return PlatformSite(
        platform_id="amazon_kdp", region="global", platform_name="Amazon KDP",
        entry_type="self_publish", primary_url="https://kdp.amazon.com/",
        signup_url="https://kdp.amazon.com/signin", api_available=False,
        automation_level="assisted_browser",
        human_gates=["captcha", "tax_info", "final_submit"],
    )


def _book():
    return {"book_id": "zz1", "title": "제로존", "author": "ATA",
            "description": "소개", "price_usd": "9.99", "language": "ko"}


class TestAssistant(unittest.TestCase):
    def setUp(self):
        # 셀렉터 매핑을 임시로 채워 자동 단계가 요소를 찾도록
        import tempfile
        self.store = MappingStore(tempfile.mkdtemp())
        for key in ("title", "subtitle", "author", "description", "keywords",
                    "categories", "language", "isbn", "price",
                    "manuscript_file", "cover_file"):
            self.store.set_field("amazon_kdp", key, "css", f"#{key}")

    def test_dry_run_without_driver(self):
        plan = build_publish_plan(_book(), _site(), {"epub": "/tmp/x.epub"})
        a = SeleniumAssistant(driver=None, mapping_store=self.store)
        results = a.execute(plan)
        rep = SeleniumAssistant.report(results)
        # 사람 로그인/게이트에서 정지 → 이후 단계는 실행되지 않음
        self.assertTrue(rep["halted"])
        self.assertEqual(results[0].step.action, "open_url")

    def test_auto_steps_use_driver_humangates_do_not(self):
        plan = build_publish_plan(_book(), _site(), {"epub": "/tmp/x.epub", "cover": "/tmp/c.jpg"})
        drv = FakeDriver()
        # confirm 가 항상 True → 사람이 처리했다고 보고 끝까지 진행(테스트용)
        a = SeleniumAssistant(driver=drv, mapping_store=self.store, confirm=lambda step: True)
        results = a.execute(plan)
        rep = SeleniumAssistant.report(results)
        # open_url 은 드라이버로 실행
        self.assertIn("https://kdp.amazon.com/", drv.gets)
        # fill/upload 가 요소를 찾았음
        self.assertTrue(len(drv.find_calls) >= 3)
        # 파일 업로드 경로가 전송됨
        self.assertIn("/tmp/x.epub", drv._el.sent)
        # 사람 게이트는 done(confirm True) 이지만 브라우저로 자동 클릭하지 않았음:
        # find_element 호출 수가 자동(fill/upload/price) 단계 수와 일치(게이트는 미포함)
        auto_field_steps = [s for s in plan.steps
                            if s.action in ("fill", "upload", "select", "click_safe")]
        self.assertEqual(len(drv.find_calls), len(auto_field_steps))
        # 마지막 단계는 final_submit 게이트
        self.assertEqual(results[-1].step.gate, "final_submit")

    def test_human_gate_halts_when_not_confirmed(self):
        plan = build_publish_plan(_book(), _site(), {})
        drv = FakeDriver()
        # confirm False → 첫 사람 개입(wait_human_login)에서 정지
        a = SeleniumAssistant(driver=drv, mapping_store=self.store, confirm=lambda step: False)
        results = a.execute(plan)
        self.assertEqual(results[-1].status, "halted_for_human")
        # 로그인 정지 → 자동 fill 단계까지 가지 못함(드라이버 get 만 1회)
        self.assertEqual(drv.gets, ["https://kdp.amazon.com/"])

    def test_unmapped_field_skipped_not_fatal(self):
        # 일부 칸 매핑이 없으면 그 칸만 건너뛰고 나머지는 계속 채워야 한다.
        import tempfile
        partial = MappingStore(tempfile.mkdtemp())
        for key in ("title", "author", "manuscript_file"):  # description/price 등은 일부러 누락
            partial.set_field("amazon_kdp", key, "css", f"#{key}")
        plan = build_publish_plan(_book(), _site(), {"epub": "/tmp/x.epub"})
        drv = FakeDriver()
        a = SeleniumAssistant(driver=drv, mapping_store=partial, confirm=lambda s: True)
        results = a.execute(plan)
        statuses = {(r.step.field_key): r.status for r in results if r.step.action == "fill"}
        self.assertEqual(statuses.get("title"), "done")
        self.assertEqual(statuses.get("description"), "skipped")  # 매핑 없음 → 건너뜀
        # 중단되지 않고 끝까지 진행(마지막은 최종 게이트)
        self.assertEqual(results[-1].step.gate, "final_submit")
        self.assertNotIn("error", [r.status for r in results])

    def test_unknown_action_blocked(self):
        from selenium_bot.models import PlanStep, PublishPlan
        from selenium_bot import gates
        plan = PublishPlan(platform_id="x", book_id="x",
                           steps=[PlanStep(action="delete_account")])
        a = SeleniumAssistant(driver=FakeDriver(), mapping_store=self.store)
        with self.assertRaises(gates.HumanGateError):
            a.execute(plan)


if __name__ == "__main__":
    unittest.main()
