import unittest

from ebook_polisher.models import Chunk
from ebook_polisher.verifier import (
    verify_chunk_plan,
    verify_polished_blocks,
    preserve_check,
    forbidden_change_report,
)


class TestPreserveCheck(unittest.TestCase):
    def test_numbers_kept(self):
        raw = "1947년에 출간된 책은 320쪽이며 가격은 12,000원이다."
        polished = "1947년에 출간된 그 책은 무려 320쪽이고, 가격은 12,000원이었다."
        res = preserve_check(raw, polished)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["missing_numbers"], [])
        self.assertGreaterEqual(res["length_ratio"], 0.5)

    def test_number_dropped(self):
        raw = "전체 320쪽 중 12장으로 구성되었다."
        polished = "전체 쪽수가 꽤 되며 여러 장으로 구성되었다."
        res = preserve_check(raw, polished)
        self.assertFalse(res["ok"], res)
        self.assertIn("320", res["missing_numbers"])
        self.assertIn("12", res["missing_numbers"])

    def test_length_ratio_too_short(self):
        raw = "아주 긴 원문 텍스트가 여기에 있다. " * 10
        polished = "짧음."
        res = preserve_check(raw, polished)
        self.assertFalse(res["ok"], res)
        self.assertLess(res["length_ratio"], 0.5)

    def test_tokens_acronym_url(self):
        raw = "참고: https://example.com 의 NASA 자료 ISBN 978-89-12345-67-8 참조."
        polished = "여기를 보세요. 자료 출처가 빠졌습니다."
        res = preserve_check(raw, polished)
        self.assertIn("NASA", res["missing_tokens"])


class TestVerifyPolishedBlocks(unittest.TestCase):
    def test_exact_match(self):
        res = verify_polished_blocks(["b1", "b2"], ["b2", "b1"])
        self.assertTrue(res["ok"])
        self.assertEqual(res["missing"], [])
        self.assertEqual(res["extra"], [])

    def test_missing_and_extra(self):
        res = verify_polished_blocks(["b1", "b2", "b3"], ["b1", "b4"])
        self.assertFalse(res["ok"])
        self.assertEqual(res["missing"], ["b2", "b3"])
        self.assertEqual(res["extra"], ["b4"])


class TestForbiddenChangeReport(unittest.TestCase):
    def test_flags_changed_number(self):
        raw = "정가는 15,000원입니다."
        polished = "정가는 16,000원입니다."  # 숫자 변경
        res = forbidden_change_report(raw, polished, ["number"])
        self.assertFalse(res["ok"], res)
        self.assertTrue(any(v["type"] == "number" for v in res["violations"]))

    def test_ok_when_number_kept(self):
        raw = "정가는 15,000원입니다."
        polished = "정가는 15,000원으로 책정되었습니다."
        res = forbidden_change_report(raw, polished, ["number"])
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["violations"], [])


class TestVerifyChunkPlan(unittest.TestCase):
    def test_overlap_only_fails(self):
        # b3 이 어떤 primary 에도 없고 overlap 에만 존재 -> ok False.
        chunks = [
            Chunk("chunk_000001", ["b1", "b2"], ["b3"], 0, 0, 10),
        ]
        res = verify_chunk_plan(["b1", "b2", "b3"], chunks)
        self.assertFalse(res["ok"])
        self.assertEqual(res["overlap_only"], ["b3"])

    def test_clean_plan(self):
        chunks = [
            Chunk("chunk_000001", ["b1", "b2"], ["b2"], 0, 0, 10),
            Chunk("chunk_000002", ["b3"], [], 0, 0, 10),
        ]
        # b2 은 overlap 으로도 등장하지만 primary 에도 있으므로 overlap_only 아님.
        res = verify_chunk_plan(["b1", "b2", "b3"], chunks)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["coverage_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
