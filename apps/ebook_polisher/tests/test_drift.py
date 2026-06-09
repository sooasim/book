"""Style Drift Detector 테스트 (docs/07 §9)."""
from __future__ import annotations

import unittest

from ebook_polisher.drift import (
    detect_drift,
    drift_report,
    split_sentences,
    style_vector,
)
from ebook_polisher.models import Block


def _para(idx: int, text: str) -> Block:
    return Block(
        block_id=f"b{idx}",
        page_id="p1",
        order_index=idx,
        block_type="paragraph",
        text=text,
    )


class TestSplitSentences(unittest.TestCase):
    def test_korean_split(self):
        sents = split_sentences("오늘은 맑다. 내일은 비가 온다.")
        self.assertEqual(len(sents), 2)

    def test_empty(self):
        self.assertEqual(split_sentences(""), [])
        self.assertEqual(split_sentences("   "), [])


class TestStyleVector(unittest.TestCase):
    def test_two_sentences(self):
        v = style_vector("오늘은 맑다. 내일은 흐리다.")
        self.assertEqual(v["sentence_count"], 2)
        self.assertGreater(v["avg_sentence_len"], 0.0)
        # 평균 문장 길이는 합리적인 범위.
        self.assertLess(v["avg_sentence_len"], 30)
        # ending_dist 비율 합은 ~1.
        self.assertAlmostEqual(sum(v["ending_dist"].values()), 1.0, places=6)

    def test_empty_text(self):
        v = style_vector("")
        self.assertEqual(v["sentence_count"], 0)
        self.assertEqual(v["avg_sentence_len"], 0.0)
        self.assertEqual(v["comma_rate"], 0.0)
        self.assertEqual(v["quote_ratio"], 0.0)
        self.assertAlmostEqual(sum(v["ending_dist"].values()), 0.0, places=6)

    def test_quote_ratio(self):
        v = style_vector('그는 “안녕”이라 말했다. 나는 웃었다.')
        self.assertEqual(v["sentence_count"], 2)
        self.assertAlmostEqual(v["quote_ratio"], 0.5, places=6)

    def test_comma_rate(self):
        v = style_vector("사과, 배, 감을 샀다.")
        self.assertEqual(v["sentence_count"], 1)
        self.assertEqual(v["comma_rate"], 2.0)


class TestDetectDrift(unittest.TestCase):
    def _similar_blocks(self):
        texts = [
            "오늘은 맑다. 내일은 흐리다.",
            "비가 온다. 우산을 챙긴다.",
            "바람이 분다. 나무가 흔들린다.",
            "해가 진다. 별이 뜬다.",
            "강이 흐른다. 물이 차다.",
            "산이 높다. 길이 멀다.",
        ]
        return [_para(i, t) for i, t in enumerate(texts)]

    def test_similar_blocks_ok(self):
        res = detect_drift(self._similar_blocks())
        self.assertTrue(res["ok"])
        self.assertEqual(res["outliers"], [])
        self.assertEqual(res["n"], 6)

    def test_long_block_is_outlier(self):
        blocks = self._similar_blocks()
        long_text = "그리고 " * 150  # 마침표 없는 약 600자 한 문장.
        self.assertGreater(len(long_text), 500)
        blocks.append(_para(99, long_text))

        res = detect_drift(blocks)
        self.assertFalse(res["ok"])
        ids = [o["block_id"] for o in res["outliers"]]
        self.assertIn("b99", ids)
        outlier = next(o for o in res["outliers"] if o["block_id"] == "b99")
        self.assertGreater(abs(outlier["z"]), 2.0)

    def test_fewer_than_two_blocks_ok(self):
        self.assertTrue(detect_drift([])["ok"])
        self.assertEqual(detect_drift([])["n"], 0)
        one = [_para(0, "오늘은 맑다.")]
        res = detect_drift(one)
        self.assertTrue(res["ok"])
        self.assertEqual(res["n"], 1)
        self.assertEqual(res["outliers"], [])

    def test_ignores_non_paragraph(self):
        b = Block(block_id="t1", page_id="p1", order_index=0,
                  block_type="title", text="제목")
        res = detect_drift([b])
        self.assertEqual(res["n"], 0)
        self.assertTrue(res["ok"])

    def test_uses_polished_text(self):
        b = _para(0, "원문이다.")
        b.polished_text = "윤문된 더 긴 문장이다."
        v = style_vector(b.polished_text or b.text)
        self.assertEqual(v["sentence_count"], 1)


class TestDriftReport(unittest.TestCase):
    def test_report_shape(self):
        blocks = [_para(i, "오늘은 맑다. 내일은 흐리다.") for i in range(3)]
        rep = drift_report(blocks)
        self.assertIn("ok", rep)
        self.assertIn("drift", rep)
        self.assertEqual(rep["n_prose"], 3)
        self.assertEqual(rep["ok"], rep["drift"]["ok"])

    def test_report_no_prose(self):
        rep = drift_report([])
        self.assertEqual(rep["n_prose"], 0)
        self.assertTrue(rep["ok"])


if __name__ == "__main__":
    unittest.main()
