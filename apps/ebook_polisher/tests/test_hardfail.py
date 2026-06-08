"""ebook_polisher.hardfail 단위 테스트."""
import unittest

from ebook_polisher.hardfail import lint


class TestHardfail(unittest.TestCase):
    def test_ok_text_passes(self):
        report = lint("정상 문장입니다. 그는 천천히 걸었다.")
        self.assertTrue(report["ok"])
        self.assertEqual(report["failures"], [])

    def test_forbidden_critical_fails(self):
        report = lint("결론적으로 말하자면 이것은 좋다.")
        self.assertFalse(report["ok"])
        codes = [f["code"] for f in report["failures"]]
        self.assertIn("forbidden_critical", codes)

    def test_unbalanced_paren_fails(self):
        report = lint("괄호가 열렸지만 닫히지 않았다 (예시")
        self.assertFalse(report["ok"])
        codes = [f["code"] for f in report["failures"]]
        self.assertIn("bracket_mismatch", codes)

    def test_unclosed_bold_fails(self):
        report = lint("굵게 **가 닫히지 않음")
        self.assertFalse(report["ok"])
        codes = [f["code"] for f in report["failures"]]
        self.assertIn("md_bold_unclosed", codes)

    def test_empty_fails(self):
        report = lint("")
        self.assertFalse(report["ok"])
        codes = [f["code"] for f in report["failures"]]
        self.assertIn("empty_chunk", codes)

    def test_report_shape(self):
        report = lint("정상 문장입니다.")
        self.assertIn("ok", report)
        self.assertIn("failures", report)
        self.assertIn("warnings", report)
        self.assertIn("stats", report)


if __name__ == "__main__":
    unittest.main()
