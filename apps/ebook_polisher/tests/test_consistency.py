"""일관성 패스(Consistency Pass) 테스트."""
from __future__ import annotations

import unittest

from ebook_polisher.consistency import (
    classify_ending,
    consistency_report,
    detect_honorific_drift,
    detect_term_variants,
)
from ebook_polisher.models import Block


def _p(block_id: str, text: str) -> Block:
    """문단 블록 헬퍼."""
    return Block(
        block_id=block_id,
        page_id="pg1",
        order_index=0,
        block_type="paragraph",
        text=text,
    )


class TestClassifyEnding(unittest.TestCase):
    def test_formal(self):
        self.assertEqual(classify_ending("이것은 사실입니다."), "formal")
        self.assertEqual(classify_ending("정말 그렇습니까?"), "formal")

    def test_polite(self):
        self.assertEqual(classify_ending("저는 갑니다요"), "polite")
        self.assertEqual(classify_ending("정말 좋아요."), "polite")
        self.assertEqual(classify_ending("그것은 사과예요."), "polite")
        self.assertEqual(classify_ending("여기에 있어요!"), "polite")

    def test_plain(self):
        self.assertEqual(classify_ending("이것은 사실이다."), "plain")
        self.assertEqual(classify_ending("그는 떠났다."), "plain")
        self.assertEqual(classify_ending("그가 온다."), "plain")

    def test_other(self):
        self.assertEqual(classify_ending("리만 가설"), "other")
        self.assertEqual(classify_ending(""), "other")
        self.assertEqual(classify_ending("   "), "other")

    def test_strips_trailing_quotes(self):
        self.assertEqual(classify_ending('"그는 떠났다."'), "plain")
        self.assertEqual(classify_ending("그렇습니다”"), "formal")


class TestHonorificDrift(unittest.TestCase):
    def test_plain_book_with_one_polite_block(self):
        blocks = [
            _p("b1", "그는 떠났다. 비가 내렸다."),
            _p("b2", "산이 높다. 강이 깊다."),
            _p("b3", "별이 빛난다. 바람이 분다."),
            _p("b4", "달이 밝다. 하늘이 맑다."),
            _p("b5", "저는 여기 있어요. 정말 좋아요."),  # polite 이탈
        ]
        r = detect_honorific_drift(blocks)
        self.assertEqual(r["dominant"], "plain")
        self.assertIn("b5", r["deviating_block_ids"])
        self.assertNotIn("b1", r["deviating_block_ids"])
        # 5블록 중 1블록 이탈 → 0.2 미만이므로 ok True.
        self.assertTrue(r["ok"])

    def test_uniform_book_ok_and_empty(self):
        blocks = [
            _p("b1", "그는 떠났다. 비가 내렸다."),
            _p("b2", "산이 높다. 강이 깊다."),
        ]
        r = detect_honorific_drift(blocks)
        self.assertEqual(r["dominant"], "plain")
        self.assertEqual(r["deviating_block_ids"], [])
        self.assertTrue(r["ok"])

    def test_no_prose_blocks_ok(self):
        blocks = [
            Block("t1", "pg1", 0, "title", "제목입니다"),
        ]
        r = detect_honorific_drift(blocks)
        self.assertTrue(r["ok"])
        self.assertEqual(r["deviating_block_ids"], [])

    def test_high_deviation_not_ok(self):
        blocks = [
            _p("b1", "그는 떠났다."),
            _p("b2", "저는 좋아요."),
            _p("b3", "정말 그렇습니다."),
        ]
        r = detect_honorific_drift(blocks)
        # 지배 문체가 무엇이든 3블록 중 2블록 이상 이탈 → ok False.
        self.assertFalse(r["ok"])

    def test_only_paragraph_analyzed(self):
        blocks = [
            _p("b1", "그는 떠났다."),
            _p("b2", "비가 내렸다."),
            Block("q1", "pg1", 0, "quote", "저는 좋아요."),  # 산문 아님 → 무시
        ]
        r = detect_honorific_drift(blocks)
        self.assertEqual(r["deviating_block_ids"], [])


class TestTermVariants(unittest.TestCase):
    def test_glossary_violation(self):
        blocks = [_p("b1", "이 책은 리만가설을 다룬다.")]
        r = detect_term_variants(blocks, {"리만 가설": ["리만가설"]})
        self.assertEqual(len(r["violations"]), 1)
        v = r["violations"][0]
        self.assertEqual(v["block_id"], "b1")
        self.assertEqual(v["found"], "리만가설")
        self.assertEqual(v["canonical"], "리만 가설")
        self.assertFalse(r["ok"])

    def test_no_violation_when_canonical_used(self):
        blocks = [_p("b1", "이 책은 리만 가설을 다룬다.")]
        r = detect_term_variants(blocks, {"리만 가설": ["리만가설"]})
        self.assertEqual(r["violations"], [])
        self.assertTrue(r["ok"])

    def test_auto_cluster_spacing_variants(self):
        blocks = [
            _p("b1", "리만가설 은 어렵다."),
            _p("b2", "리만 가설 을 증명한다."),
        ]
        r = detect_term_variants(blocks)
        keys = [c["key"] for c in r["variant_clusters"]]
        self.assertIn("리만가설", keys)
        cluster = next(c for c in r["variant_clusters"] if c["key"] == "리만가설")
        self.assertIn("리만가설", cluster["forms"])
        self.assertIn("리만 가설", cluster["forms"])
        self.assertGreaterEqual(len(cluster["forms"]), 2)
        self.assertEqual(cluster["block_ids"], ["b1", "b2"])

    def test_no_cluster_when_consistent(self):
        blocks = [
            _p("b1", "리만 가설은 어렵다."),
            _p("b2", "리만 가설을 다룬다."),
        ]
        r = detect_term_variants(blocks)
        keys = [c["key"] for c in r["variant_clusters"]]
        self.assertNotIn("리만가설", keys)


class TestConsistencyReport(unittest.TestCase):
    def test_combines_ok(self):
        blocks = [
            _p("b1", "그는 떠났다. 비가 내렸다."),
            _p("b2", "산이 높다. 강이 깊다."),
        ]
        r = consistency_report(blocks)
        self.assertTrue(r["ok"])
        self.assertIn("honorific", r)
        self.assertIn("terminology", r)
        self.assertTrue(r["honorific"]["ok"])
        self.assertTrue(r["terminology"]["ok"])

    def test_combines_not_ok_on_terminology(self):
        blocks = [
            _p("b1", "그는 떠났다."),
            _p("b2", "리만가설을 다룬다."),
        ]
        r = consistency_report(blocks, {"리만 가설": ["리만가설"]})
        self.assertFalse(r["ok"])
        self.assertFalse(r["terminology"]["ok"])

    def test_combines_not_ok_on_honorific(self):
        blocks = [
            _p("b1", "그는 떠났다."),
            _p("b2", "저는 좋아요."),
            _p("b3", "정말 그렇습니다."),
        ]
        r = consistency_report(blocks)
        self.assertFalse(r["honorific"]["ok"])
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
