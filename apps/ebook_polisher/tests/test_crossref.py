"""앵커 참조 검증(Cross-reference Validation) 테스트.

dedupe 정책 메모: find_references는 (kind, num) 쌍을 블록(텍스트) 단위로
중복 제거하여 처음 등장한 raw를 보존한다. 따라서 한 블록에서 "3장"이 두 번
나와도 참조 목록과 total_refs에는 1로만 반영된다. 서로 다른 블록에 같은
참조가 있으면 블록마다 각각 1씩 세어진다.
"""
from __future__ import annotations

import unittest

from ebook_polisher.crossref import (
    crossref_report,
    find_references,
    validate_references,
)
from ebook_polisher.models import Block


def _b(block_id: str, text: str, page_id: str = "p000001") -> Block:
    """문단 블록 헬퍼 (유효한 id 규약: bNNNNNN / pNNNNNN)."""
    return Block(
        block_id=block_id,
        page_id=page_id,
        order_index=0,
        block_type="paragraph",
        text=text,
    )


class TestFindReferences(unittest.TestCase):
    def test_basic_mix(self):
        refs = find_references("앞서 3장과 제5장 참조, 2절도")
        self.assertEqual(
            refs,
            [
                {"kind": "chapter", "num": 3, "raw": "3장"},
                {"kind": "chapter", "num": 5, "raw": "제5장"},
                {"kind": "section", "num": 2, "raw": "2절"},
            ],
        )

    def test_year_alone_no_refs(self):
        self.assertEqual(find_references("2026년"), [])
        self.assertEqual(find_references("그해 2026년에 일어난 일이다."), [])

    def test_spaces_in_reference(self):
        refs = find_references("제 3 장")
        self.assertEqual(refs, [{"kind": "chapter", "num": 3, "raw": "제 3 장"}])

    def test_order_of_appearance(self):
        refs = find_references("먼저 2절을 보고, 그다음 4장을 보라")
        self.assertEqual([r["kind"] for r in refs], ["section", "chapter"])
        self.assertEqual([r["num"] for r in refs], [2, 4])

    def test_empty(self):
        self.assertEqual(find_references(""), [])
        self.assertEqual(find_references(None), [])  # type: ignore[arg-type]


class TestDedupe(unittest.TestCase):
    def test_same_chapter_twice_counted_once(self):
        # 같은 텍스트 안의 "3장"이 두 번 → 참조 목록에 한 번만.
        refs = find_references("3장에서 다루고, 다시 3장에서 강조한다")
        self.assertEqual(refs, [{"kind": "chapter", "num": 3, "raw": "3장"}])

    def test_first_raw_kept(self):
        # 처음 등장한 raw("제3장")가 보존되어야 한다.
        refs = find_references("제3장 그리고 3장")
        self.assertEqual(refs, [{"kind": "chapter", "num": 3, "raw": "제3장"}])


class TestValidateReferences(unittest.TestCase):
    def test_chapter_over_limit_violation(self):
        blocks = [_b("b000001", "자세한 내용은 7장을 보라")]
        res = validate_references(blocks, n_chapters=5)
        self.assertFalse(res["ok"])
        self.assertEqual(res["total_refs"], 1)
        self.assertEqual(res["chapters"], 5)
        self.assertEqual(len(res["violations"]), 1)
        v = res["violations"][0]
        self.assertEqual(v["block_id"], "b000001")
        self.assertEqual(v["kind"], "chapter")
        self.assertEqual(v["num"], 7)
        self.assertEqual(v["raw"], "7장")

    def test_chapter_in_range_ok(self):
        blocks = [_b("b000002", "앞서 3장에서 다룬 것처럼")]
        res = validate_references(blocks, n_chapters=5)
        self.assertTrue(res["ok"])
        self.assertEqual(res["violations"], [])
        self.assertEqual(res["total_refs"], 1)

    def test_chapter_zero_violation(self):
        blocks = [_b("b000003", "0장 참조")]
        res = validate_references(blocks, n_chapters=5)
        self.assertFalse(res["ok"])
        self.assertEqual(len(res["violations"]), 1)
        self.assertEqual(res["violations"][0]["num"], 0)

    def test_section_validation_when_count_given(self):
        blocks = [_b("b000004", "9절을 보라")]
        # 절 수 한계 없으면 절은 검증하지 않음 → ok
        res_none = validate_references(blocks, n_chapters=5)
        self.assertTrue(res_none["ok"])
        # 장당 절 수 3 → 9절은 위반
        res = validate_references(blocks, n_chapters=5, n_sections_per_chapter=3)
        self.assertFalse(res["ok"])
        self.assertEqual(res["violations"][0]["kind"], "section")
        self.assertEqual(res["violations"][0]["num"], 9)

    def test_section_in_range_ok(self):
        blocks = [_b("b000005", "2절 참조")]
        res = validate_references(blocks, n_chapters=5, n_sections_per_chapter=3)
        self.assertTrue(res["ok"])

    def test_uses_polished_text_when_present(self):
        b = _b("b000006", "3장 참조")
        b.polished_text = "7장 참조"
        res = validate_references([b], n_chapters=5)
        self.assertFalse(res["ok"])
        self.assertEqual(res["violations"][0]["num"], 7)

    def test_total_refs_dedup_within_block(self):
        # 한 블록의 같은 참조 중복 → total_refs 1
        blocks = [_b("b000007", "3장 그리고 또 3장")]
        res = validate_references(blocks, n_chapters=5)
        self.assertEqual(res["total_refs"], 1)
        self.assertTrue(res["ok"])

    def test_same_ref_across_blocks_counted_per_block(self):
        blocks = [
            _b("b000008", "3장 참조"),
            _b("b000009", "3장 참조"),
        ]
        res = validate_references(blocks, n_chapters=5)
        self.assertEqual(res["total_refs"], 2)

    def test_empty_blocks(self):
        res = validate_references([], n_chapters=5)
        self.assertTrue(res["ok"])
        self.assertEqual(res["total_refs"], 0)
        self.assertEqual(res["violations"], [])


class TestCrossrefReport(unittest.TestCase):
    def test_wrapper_adds_checked(self):
        blocks = [_b("b000010", "3장 참조")]
        res = crossref_report(blocks, n_chapters=5)
        self.assertTrue(res["checked"])
        self.assertTrue(res["ok"])
        self.assertIn("violations", res)

    def test_wrapper_reports_violations(self):
        blocks = [_b("b000011", "7장 참조")]
        res = crossref_report(blocks, n_chapters=5)
        self.assertTrue(res["checked"])
        self.assertFalse(res["ok"])
        self.assertEqual(len(res["violations"]), 1)

    def test_zero_chapters_not_checked(self):
        blocks = [_b("b000012", "7장 참조")]
        res = crossref_report(blocks, n_chapters=0)
        self.assertFalse(res["checked"])
        self.assertTrue(res["ok"])
        self.assertEqual(res["total_refs"], 0)
        self.assertEqual(res["violations"], [])

    def test_negative_chapters_not_checked(self):
        res = crossref_report([_b("b000013", "3장")], n_chapters=-1)
        self.assertFalse(res["checked"])
        self.assertTrue(res["ok"])


class TestDeterminism(unittest.TestCase):
    def test_find_references_deterministic(self):
        text = "1장, 2절, 제3장, 4절, 5장을 두루 본다. 다시 1장."
        first = find_references(text)
        for _ in range(5):
            self.assertEqual(find_references(text), first)

    def test_validate_deterministic(self):
        blocks = [
            _b("b000014", "7장과 0장 그리고 3장"),
            _b("b000015", "9절 참조"),
        ]
        first = validate_references(blocks, n_chapters=5, n_sections_per_chapter=3)
        for _ in range(5):
            self.assertEqual(
                validate_references(blocks, n_chapters=5, n_sections_per_chapter=3),
                first,
            )


if __name__ == "__main__":
    unittest.main()
