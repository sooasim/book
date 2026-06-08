"""엣지케이스 회귀 테스트 (사이클3 검수 반영).

- 빈/블록없는 입력이 크래시하지 않고 ok 빈 산출.
- 숫자 보존 위반 시 QA blocking 게이트로 출력 불가(ok False).
- 거대 단일 블록(>max_tokens)도 누락 없이 처리.
- 비표준 page_id Parser 가 와도 청킹이 깨지지 않음.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ebook_polisher.cli import build_pipeline
from ebook_polisher.models import PolishedBlock, PolishResult
from ebook_polisher.parser import TextParser
from ebook_polisher.pipeline import EbookPolisherPipeline
from ebook_polisher.repository import SQLiteRepository


def _write(text: str) -> str:
    d = tempfile.mkdtemp()
    p = Path(d) / "m.md"
    p.write_text(text, encoding="utf-8")
    return str(p)


class CorruptingPolisher:
    """숫자를 망가뜨리는 가짜 폴리셔(보존 게이트 검증용)."""

    def polish(self, payload: dict, style_bible: str = "") -> PolishResult:
        blocks = []
        for sb in payload["source_blocks"]:
            corrupted = sb["text"].replace("2026", "9999")  # 숫자 변조
            blocks.append(PolishedBlock(block_id=sb["block_id"], polished_text=corrupted))
        return PolishResult(chunk_id=payload["chunk_id"], polished_blocks=blocks)


class TestEdgeCases(unittest.TestCase):
    def test_empty_file_no_crash(self):
        result = build_pipeline("rules", ":memory:", tempfile.mkdtemp()).run(_write(""))
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["pipeline"]["coverage_gate"]["ok"])
        self.assertEqual(result["pipeline"]["blocks"], 0)

    def test_whitespace_only_file_no_crash(self):
        result = build_pipeline("rules", ":memory:", tempfile.mkdtemp()).run(_write("   \n\n  \n"))
        self.assertTrue(result["ok"], result)

    def test_number_corruption_blocks_output(self):
        out = tempfile.mkdtemp()
        pipe = EbookPolisherPipeline(
            TextParser(), CorruptingPolisher(), SQLiteRepository(out_dir=out))
        result = pipe.run(_write("# 장\n\n제로존은 2026년에 정리되었다.\n"))
        # 무결성(coverage)은 OK 지만 숫자 보존 위반 → 출판 불가
        self.assertFalse(result["ok"], "숫자 변조는 QA blocking 으로 막아야 한다")
        self.assertIn("04_numbers_preserved", result["qa"]["blocking_failed"])

    def test_giant_block_not_dropped(self):
        giant = "가나다 " * 20000  # 매우 긴 단일 문단
        result = build_pipeline("rules", ":memory:", tempfile.mkdtemp()).run(_write(giant))
        self.assertTrue(result["ok"])
        self.assertTrue(result["coverage"]["ok"])
        self.assertEqual(result["coverage"]["missing"], [])

    def test_nonstandard_page_id_chunking(self):
        from ebook_polisher.chunker import _page_num
        self.assertEqual(_page_num("p000123"), 123)
        self.assertEqual(_page_num(""), 0)
        self.assertEqual(_page_num("xyz"), 0)
        self.assertEqual(_page_num("page-7"), 7)


if __name__ == "__main__":
    unittest.main()
