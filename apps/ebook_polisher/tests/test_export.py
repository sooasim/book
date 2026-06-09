"""export 모듈 테스트.

써드파티 라이브러리(python-docx, reportlab)는 이 환경에 없을 수 있으므로
가용성을 로컬 import 플래그로 판단하고 skipUnless 로 보호한다.
"""
import tempfile
import unittest
from pathlib import Path

from ebook_polisher import export

try:
    import docx  # noqa: F401
    _docx_available = True
except Exception:
    _docx_available = False

try:
    import reportlab  # noqa: F401
    _pdf_available = True
except Exception:
    _pdf_available = False


BLOCKS = [
    ("title", "# 제목"),
    ("paragraph", "첫 문단입니다.\n둘째 줄."),
    ("paragraph", "특수문자 <tag> & 'quote'"),
]


class TestAvailableFormats(unittest.TestCase):
    def test_md_and_epub_always_true(self):
        fmts = export.available_formats()
        self.assertIsInstance(fmts, dict)
        self.assertTrue(fmts["md"])
        self.assertTrue(fmts["epub"])

    def test_docx_pdf_match_import_availability(self):
        fmts = export.available_formats()
        self.assertEqual(fmts["docx"], _docx_available)
        # PDF 는 stdlib minipdf 폴백으로 항상 가능. 품질만 라이브러리에 따라 달라진다.
        self.assertTrue(fmts["pdf"])
        self.assertEqual(fmts["pdf_quality"], "rich" if _pdf_available else "basic")

    def test_export_pdf_fallback_always_works(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "b.pdf")
            export.export_pdf([("title", "# 1장"), ("paragraph", "본문 2026.")], path, title="t")
            with open(path, "rb") as f:
                self.assertEqual(f.read(5), b"%PDF-")


class TestWriteMarkdown(unittest.TestCase):
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "out.md")
            export.write_markdown("# Hello\n\nWorld", path)
            self.assertTrue(Path(path).exists())
            self.assertEqual(Path(path).read_text(encoding="utf-8"), "# Hello\n\nWorld")


class TestDocx(unittest.TestCase):
    @unittest.skipUnless(_docx_available, "python-docx 미설치")
    def test_blocks_to_docx(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "out.docx")
            export.blocks_to_docx(BLOCKS, path, title="책 제목")
            self.assertTrue(Path(path).exists())
            self.assertGreater(Path(path).stat().st_size, 0)

    @unittest.skipIf(_docx_available, "python-docx 설치됨 — 결측 동작 테스트 불가")
    def test_blocks_to_docx_missing_raises(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "out.docx")
            with self.assertRaises(RuntimeError):
                export.blocks_to_docx(BLOCKS, path)


class TestPdf(unittest.TestCase):
    @unittest.skipUnless(_pdf_available, "reportlab 미설치")
    def test_blocks_to_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "out.pdf")
            export.blocks_to_pdf(BLOCKS, path, title="책 제목")
            self.assertTrue(Path(path).exists())
            with open(path, "rb") as f:
                self.assertTrue(f.read(4).startswith(b"%PDF"))

    @unittest.skipIf(_pdf_available, "reportlab 설치됨 — 결측 동작 테스트 불가")
    def test_blocks_to_pdf_missing_raises(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "out.pdf")
            with self.assertRaises(RuntimeError):
                export.blocks_to_pdf(BLOCKS, path)


if __name__ == "__main__":
    unittest.main()
