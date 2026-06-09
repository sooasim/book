"""EPUB3 출력기 테스트 — stdlib zipfile 로 유효성 검증."""
from __future__ import annotations

import tempfile
import unittest
import xml.dom.minidom as minidom
import zipfile
from pathlib import Path

from ebook_polisher.epub_export import write_epub, write_html

BLOCKS = [
    ("title", "# 1장 서론"),
    ("paragraph", "제로존은 2026년에 정리되었다."),
    ("quote", "인용문 보존."),
    ("title", "# 2장 본론"),
    ("paragraph", "ISBN 978-89-12345-67-8 유지."),
]


class TestEpubExport(unittest.TestCase):
    def _make(self):
        path = str(Path(tempfile.mkdtemp()) / "book.epub")
        return write_epub(BLOCKS, path, title="제로존", author="ATA", language="ko")

    def test_valid_zip_and_mimetype_first_stored(self):
        path = self._make()
        with zipfile.ZipFile(path) as zf:
            self.assertIsNone(zf.testzip())
            names = zf.namelist()
            # mimetype 이 첫 엔트리이며 STORED(무압축)
            self.assertEqual(names[0], "mimetype")
            info = zf.getinfo("mimetype")
            self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(zf.read("mimetype").decode(), "application/epub+zip")

    def test_required_files_present(self):
        path = self._make()
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            self.assertIn("META-INF/container.xml", names)
            self.assertIn("OEBPS/content.opf", names)
            self.assertIn("OEBPS/nav.xhtml", names)
            self.assertIn("OEBPS/text/chapter_0001.xhtml", names)
            self.assertIn("OEBPS/text/chapter_0002.xhtml", names)  # 제목 2개 → 챕터 2개

    def test_opf_wellformed_and_metadata(self):
        path = self._make()
        with zipfile.ZipFile(path) as zf:
            opf = zf.read("OEBPS/content.opf").decode("utf-8")
            minidom.parseString(opf)  # XML 파싱 가능해야 함
            self.assertIn("<dc:title>제로존</dc:title>", opf)
            self.assertIn("<dc:creator>ATA</dc:creator>", opf)
            self.assertIn('properties="nav"', opf)
            # 모든 챕터가 spine 에 등재
            self.assertEqual(opf.count("<itemref"), 2)

    def test_content_lossless(self):
        path = self._make()
        with zipfile.ZipFile(path) as zf:
            all_text = "".join(
                zf.read(n).decode("utf-8") for n in zf.namelist()
                if n.endswith(".xhtml")
            )
        self.assertIn("2026", all_text)
        self.assertIn("978-89-12345-67-8", all_text)

    def test_no_titles_single_chapter(self):
        path = str(Path(tempfile.mkdtemp()) / "b.epub")
        write_epub([("paragraph", "제목 없는 본문.")], path)
        with zipfile.ZipFile(path) as zf:
            chapters = [n for n in zf.namelist() if "chapter_" in n]
            self.assertEqual(len(chapters), 1)

    def test_xml_escape(self):
        path = str(Path(tempfile.mkdtemp()) / "e.epub")
        write_epub([("paragraph", "a < b & c > d")], path)
        with zipfile.ZipFile(path) as zf:
            ch = zf.read("OEBPS/text/chapter_0001.xhtml").decode("utf-8")
            minidom.parseString(ch)  # 이스케이프 안 되면 파싱 실패
            self.assertIn("&lt;", ch)
            self.assertIn("&amp;", ch)

    def test_write_html(self):
        path = str(Path(tempfile.mkdtemp()) / "p.html")
        write_html(BLOCKS, path, title="t")
        text = Path(path).read_text(encoding="utf-8")
        self.assertIn("<h2>1장 서론</h2>", text)
        self.assertIn("2026", text)


if __name__ == "__main__":
    unittest.main()
