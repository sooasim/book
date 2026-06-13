"""gates.py 안전 코어 테스트."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from selenium_bot import gates
from selenium_bot.gates import HumanGateError
from selenium_bot.models import HUMAN_GATES


class TestIsHumanGate(unittest.TestCase):
    def test_known_gate_true(self):
        self.assertTrue(gates.is_human_gate("final_submit"))

    def test_non_gate_false(self):
        self.assertFalse(gates.is_human_gate("fill"))

    def test_all_human_gates_recognized(self):
        for name in HUMAN_GATES:
            self.assertTrue(gates.is_human_gate(name))


class TestAssertNotAutomatable(unittest.TestCase):
    def test_gate_raises(self):
        with self.assertRaises(HumanGateError):
            gates.assert_not_automatable("captcha")

    def test_safe_action_no_raise(self):
        self.assertIsNone(gates.assert_not_automatable("fill"))


class TestGuardAction(unittest.TestCase):
    def test_automatable_action_ok(self):
        self.assertIsNone(gates.guard_action("fill"))

    def test_human_gate_marker_ok(self):
        self.assertIsNone(gates.guard_action("human_gate"))

    def test_unknown_dangerous_action_raises(self):
        with self.assertRaises(HumanGateError):
            gates.guard_action("delete_account")


class TestGateLabel(unittest.TestCase):
    def test_known_labels(self):
        self.assertEqual(gates.gate_label("account_create_final"), "회원가입 최종 완료")
        self.assertEqual(gates.gate_label("captcha"), "캡차")
        self.assertEqual(gates.gate_label("email_verify"), "이메일 인증")
        self.assertEqual(gates.gate_label("phone_verify"), "휴대폰 본인인증")
        self.assertEqual(gates.gate_label("identity_verify"), "신원/사업자 인증")
        self.assertEqual(gates.gate_label("tos_agree"), "약관 동의")
        self.assertEqual(gates.gate_label("content_rights_confirm"), "저작권/출판권 확인")
        self.assertEqual(gates.gate_label("ai_disclosure"), "AI 사용 고지")
        self.assertEqual(gates.gate_label("exclusivity"), "독점 계약")
        self.assertEqual(gates.gate_label("tax_info"), "세금 정보")
        self.assertEqual(gates.gate_label("payout_info"), "정산 계좌")
        self.assertEqual(gates.gate_label("pricing_confirm"), "가격 확정")
        self.assertEqual(gates.gate_label("final_submit"), "최종 게시")

    def test_all_gates_have_labels(self):
        for name in HUMAN_GATES:
            # 라벨은 원본과 달라야 한다(모두 매핑되어 있음).
            self.assertNotEqual(gates.gate_label(name), name)

    def test_unknown_passthrough(self):
        self.assertEqual(gates.gate_label("not_a_gate"), "not_a_gate")


class TestHumanChecklist(unittest.TestCase):
    def test_labels_and_structure(self):
        result = gates.human_checklist(["captcha", "final_submit"])
        self.assertEqual(
            result,
            [
                {"gate": "captcha", "label": "캡차", "done": False},
                {"gate": "final_submit", "label": "최종 게시", "done": False},
            ],
        )

    def test_dedupes_preserving_order(self):
        result = gates.human_checklist(
            ["captcha", "tos_agree", "captcha", "final_submit", "tos_agree"]
        )
        gate_order = [item["gate"] for item in result]
        self.assertEqual(gate_order, ["captcha", "tos_agree", "final_submit"])

    def test_empty(self):
        self.assertEqual(gates.human_checklist([]), [])


if __name__ == "__main__":
    unittest.main()
