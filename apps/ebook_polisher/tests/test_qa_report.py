"""QA 리포트 단계 테스트."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ebook_polisher.cli import build_pipeline


def _write(text: str) -> str:
    d = tempfile.mkdtemp()
    p = Path(d) / "m.md"
    p.write_text(text, encoding="utf-8")
    return str(p)


class TestQAReport(unittest.TestCase):
    def _run(self, text):
        out = tempfile.mkdtemp()
        return build_pipeline("rules", ":memory:", out).run(_write(text))

    def test_clean_doc_qa_ok(self):
        r = self._run("# 1장\n\n깨끗한 문장이다. 숫자 2026 보존.\n")
        self.assertTrue(r["qa"]["ok"])
        self.assertEqual(r["qa"]["blocking_failed"], [])
        self.assertTrue(r["qa"]["coverage"]["ok"])

    def test_hardfail_reported_not_blocking(self):
        # 금지어가 있어도 무결성(coverage)은 OK → 출력은 되되 QA에 보고된다
        r = self._run("# 1장\n\n결론적으로 말하자면 이것은 좋다.\n")
        self.assertTrue(r["ok"])                     # 무결성 통과로 출력 가능
        self.assertTrue(r["qa"]["ok"])               # blocking 아님
        self.assertIn("forbidden_critical", r["qa"]["hardfail"]["failures"])

    def test_titles_gate(self):
        r = self._run("# 제목\n\n본문.\n")
        self.assertTrue(r["qa"]["gates"]["11_titles_present"]["ok"])

    def test_hash_audit_recorded(self):
        r = self._run("# 1장\n\n본문 문장.\n")
        self.assertTrue(r["qa"]["gates"]["14_hash_audit"]["ok"])


if __name__ == "__main__":
    unittest.main()
