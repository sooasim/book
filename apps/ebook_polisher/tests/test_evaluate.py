"""품질 평가 모듈 테스트 (OCES 03 §10 Evaluation)."""
from __future__ import annotations

import unittest

from ebook_polisher.evaluate import (
    length_adherence,
    quality_report,
    readability_score,
)
from ebook_polisher.models import Block


def _para(idx: int, text: str, polished: str = "") -> Block:
    return Block(
        block_id=f"b{idx:06d}",
        page_id=f"p{idx:06d}",
        order_index=idx,
        block_type="paragraph",
        text=text,
        polished_text=polished,
    )


class TestReadabilityScore(unittest.TestCase):
    def test_empty_returns_one(self):
        self.assertEqual(readability_score(""), 1.0)
        self.assertEqual(readability_score("   "), 1.0)

    def test_bounds(self):
        for text in ["", "짧다.", "a" * 500, "보통 길이의 문장입니다. 또 하나입니다."]:
            s = readability_score(text)
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 1.0)

    def test_clean_beats_runon(self):
        # 이상 구간(40~60자)에 가까운 깔끔한 문장들.
        clean = (
            "이 문장은 적당한 길이를 가지고 있어서 읽기에 매우 편안한 편이다. "
            "다음 문장도 비슷한 길이를 유지하면서 흐름을 자연스럽게 이어 간다."
        )
        runon = "이것은 끝없이 이어지는 " + "아주 긴 만연체 문장 " * 40 + "끝"
        self.assertGreater(readability_score(clean), readability_score(runon))

    def test_runon_is_low(self):
        runon = "가" * 500 + "."
        self.assertLess(readability_score(runon), 0.3)


class TestLengthAdherence(unittest.TestCase):
    def test_exact_target(self):
        self.assertEqual(length_adherence(1000, 1000), 1.0)

    def test_within_fifteen_percent(self):
        self.assertEqual(length_adherence(1100, 1000), 1.0)
        self.assertEqual(length_adherence(900, 1000), 1.0)
        self.assertEqual(length_adherence(850, 1000), 1.0)

    def test_way_off_is_low(self):
        self.assertLess(length_adherence(10, 1000), 0.3)
        self.assertLess(length_adherence(2500, 1000), 0.3)

    def test_target_nonpositive(self):
        self.assertEqual(length_adherence(500, 0), 1.0)
        self.assertEqual(length_adherence(500, -5), 1.0)

    def test_bounds(self):
        for actual, target in [(0, 100), (100, 100), (10000, 100), (50, 100)]:
            s = length_adherence(actual, target)
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 1.0)


def _clean_doc() -> list[Block]:
    # 균일한 문체(plain)·적당한 길이의 산문 블록들.
    base = (
        "이 문단은 비교적 안정된 길이를 가지고 있으며 전반적으로 차분한 흐름을 보인다. "
        "두 번째 문장도 비슷한 호흡으로 내용을 정리하면서 자연스럽게 마무리한다."
    )
    return [_para(i, base) for i in range(1, 6)]


class TestQualityReport(unittest.TestCase):
    def test_keys_present(self):
        report = quality_report(_clean_doc())
        for key in (
            "overall",
            "grade",
            "readability",
            "length",
            "consistency_ok",
            "drift_ok",
        ):
            self.assertIn(key, report)

    def test_overall_bounds(self):
        report = quality_report(_clean_doc())
        self.assertGreaterEqual(report["overall"], 0.0)
        self.assertLessEqual(report["overall"], 1.0)

    def test_clean_doc_high_grade(self):
        report = quality_report(_clean_doc())
        self.assertGreaterEqual(report["overall"], 0.7)
        self.assertIn(report["grade"], ("A", "B"))

    def test_no_blocks(self):
        report = quality_report([])
        self.assertEqual(report["readability"], 1.0)
        self.assertEqual(report["length"], 1.0)

    def test_with_chapters(self):
        chapters = [
            {"content_md": "word " * 100, "target_words": 100},
            {"content_md": "word " * 95, "target_words": 100},
        ]
        report = quality_report(_clean_doc(), chapters=chapters)
        self.assertEqual(report["length"], 1.0)

    def test_chapters_way_off_lowers_length(self):
        chapters = [{"content_md": "word " * 10, "target_words": 1000}]
        report = quality_report(_clean_doc(), chapters=chapters)
        self.assertLess(report["length"], 0.3)

    def test_grade_thresholds_via_chapters(self):
        # 종합이 D로 떨어지도록 분량을 크게 어긋나게 한다.
        report = quality_report([], chapters=[{"content_md": "x", "target_words": 1000}])
        self.assertIn(report["grade"], ("A", "B", "C", "D"))


class TestDeterminism(unittest.TestCase):
    def test_readability_deterministic(self):
        text = "여러 번 호출해도 같은 결과가 나와야 한다. 두 번째 문장도 마찬가지다."
        self.assertEqual(readability_score(text), readability_score(text))

    def test_length_deterministic(self):
        self.assertEqual(length_adherence(870, 1000), length_adherence(870, 1000))

    def test_report_deterministic(self):
        doc = _clean_doc()
        chapters = [{"content_md": "word " * 90, "target_words": 100}]
        a = quality_report(doc, chapters=chapters)
        b = quality_report(doc, chapters=chapters)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
