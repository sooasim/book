"""통합 테스트 — 초고 → 윤문본 무손실 파이프라인(메인 교차 검증).

검증 목표(docs/07 §14 DoD):
  - page/block coverage 100%, 누락 0
  - 숫자 등 금지 변경 보존(무손실)
  - 중단→재개 시 이미 처리된 청크 재실행 0(멱등)
  - rules 모드 결정성(동일 입력 → 동일 출력)
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ebook_polisher.cli import build_pipeline
from ebook_polisher.parser import TextParser
from ebook_polisher.pipeline import EbookPolisherPipeline
from ebook_polisher.polisher import RulesPolisher
from ebook_polisher.repository import SQLiteRepository

SAMPLE = """# 1장 서론

제로존 이론은 2026년에  정리되었다.    공백이 많은   문장이다.
리만 가설은 L5 좌표와 연결된다.

> 인용문은 보존되어야 한다.

# 2장 본론

이 수치 3.141592 는 절대 바뀌면 안 된다.
ISBN 978-89-12345-67-8 도 보존 대상이다.
"""


def _write_sample(text: str = SAMPLE) -> str:
    d = tempfile.mkdtemp()
    p = Path(d) / "manuscript.md"
    p.write_text(text, encoding="utf-8")
    return str(p)


class TestIntegration(unittest.TestCase):
    def _run(self, mode="rules", db=":memory:", out=None):
        out = out or tempfile.mkdtemp()
        pipe = build_pipeline(mode, db, out)
        return pipe.run(_write_sample())

    def test_full_coverage_and_output(self):
        result = self._run()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["coverage"]["ok"])
        self.assertEqual(result["coverage"]["missing"], [])
        self.assertEqual(result["coverage"]["extra"], [])
        # source == polished 블록 수
        self.assertEqual(result["coverage"]["source"], result["coverage"]["polished"])
        self.assertTrue(result["pipeline"]["coverage_gate"]["ok"])
        self.assertTrue(Path(result["files"]["md"]).exists())

    def test_lossless_numbers_preserved(self):
        out = tempfile.mkdtemp()
        result = self._run(out=out)
        md = Path(result["files"]["md"]).read_text(encoding="utf-8")
        for token in ["2026", "3.141592", "978-89-12345-67-8", "리만 가설", "L5"]:
            self.assertIn(token, md, f"무손실 위반: {token} 누락")

    def test_whitespace_collapsed(self):
        out = tempfile.mkdtemp()
        result = self._run(out=out)
        md = Path(result["files"]["md"]).read_text(encoding="utf-8")
        # 본문 줄에 연속 2칸 공백이 없어야 한다(무손실 정리)
        for line in md.splitlines():
            if line.strip() and not line.startswith("#"):
                self.assertNotIn("  ", line, f"공백 축약 실패: {line!r}")

    def test_resume_idempotent(self):
        tmpdb = str(Path(tempfile.mkdtemp()) / "polish.db")
        out = tempfile.mkdtemp()
        src = _write_sample()
        # 1차 실행
        pipe1 = EbookPolisherPipeline(TextParser(), RulesPolisher(),
                                      SQLiteRepository(db_path=tmpdb, out_dir=out))
        r1 = pipe1.run(src)
        self.assertTrue(r1["pipeline"]["processed_chunks"] >= 1)
        # 2차 실행(같은 DB) — 이미 done 인 청크는 건너뛰어야 함
        # 같은 파일 DB 재오픈 → 이미 완료된 청크는 건너뛰어야 한다(processed_chunks==0)
        repo2 = SQLiteRepository(db_path=tmpdb, out_dir=out)
        pipe2 = EbookPolisherPipeline(TextParser(), RulesPolisher(), repo2)
        r2 = pipe2.run(src)
        self.assertEqual(r2["pipeline"]["processed_chunks"], 0,
                         "재개 시 이미 처리한 청크를 다시 처리하면 안 된다")
        self.assertTrue(r2["coverage"]["ok"])
        self.assertEqual(r1["coverage"]["source"], r2["coverage"]["source"])

    def test_determinism(self):
        out1, out2 = tempfile.mkdtemp(), tempfile.mkdtemp()
        src = _write_sample()
        p1 = EbookPolisherPipeline(TextParser(), RulesPolisher(),
                                   SQLiteRepository(out_dir=out1)).run(src)
        p2 = EbookPolisherPipeline(TextParser(), RulesPolisher(),
                                   SQLiteRepository(out_dir=out2)).run(src)
        md1 = Path(p1["files"]["md"]).read_text(encoding="utf-8")
        md2 = Path(p2["files"]["md"]).read_text(encoding="utf-8")
        self.assertEqual(md1, md2, "rules 모드는 결정적이어야 한다")

    def test_agency_mode_runs(self):
        result = self._run(mode="agency")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["coverage"]["ok"])


if __name__ == "__main__":
    unittest.main()
