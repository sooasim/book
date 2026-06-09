"""minipdf — 의존성 없는 PDF 작성기 테스트."""
from __future__ import annotations

import os
import re
import tempfile
import unittest

from ebook_polisher import minipdf


def _count_page_objects(data: bytes) -> int:
    """PDF 바이트에서 /Type /Page (Pages 가 아닌) 객체 수를 센다."""
    # /Type /Pages 는 제외하고 /Type /Page 만 센다.
    return len(re.findall(rb"/Type\s*/Page(?![s])", data))


def _trailer_size(data: bytes) -> int:
    m = re.search(rb"trailer.*?/Size\s+(\d+)", data, re.DOTALL)
    assert m, "trailer 의 /Size 를 찾을 수 없음"
    return int(m.group(1))


def _xref_object_count(data: bytes) -> int:
    """xref 테이블의 서브섹션 헤더 (start count) 를 읽어 객체 수를 구한다."""
    m = re.search(rb"xref\s*\n0\s+(\d+)\s*\n", data)
    assert m, "xref 서브섹션 헤더를 찾을 수 없음"
    return int(m.group(1))


class TestEscapePdfText(unittest.TestCase):
    def test_escape_parens_and_backslash(self):
        self.assertEqual(minipdf.escape_pdf_text("(a)\\b"), "\\(a\\)\\\\b")

    def test_korean_becomes_question_mark(self):
        self.assertEqual(minipdf.escape_pdf_text("한"), "?")
        self.assertEqual(minipdf.escape_pdf_text("a한b"), "a?b")

    def test_latin1_preserved(self):
        # codepoint <= 0xFF 는 그대로 유지 (예: é = 0xE9).
        self.assertEqual(minipdf.escape_pdf_text("café"), "café")

    def test_empty(self):
        self.assertEqual(minipdf.escape_pdf_text(""), "")


class TestPdfStructure(unittest.TestCase):
    def setUp(self):
        self.blocks = [
            ("title", "Chapter One"),
            ("body", "This is a body paragraph with some text."),
            ("body", "Another paragraph here."),
        ]
        self.data = minipdf.pdf_bytes(self.blocks, title="My Book")

    def test_header(self):
        self.assertTrue(self.data.startswith(b"%PDF-"))

    def test_eof(self):
        self.assertIn(b"%%EOF", self.data)

    def test_has_xref(self):
        self.assertIn(b"xref", self.data)

    def test_has_trailer_with_root(self):
        self.assertIn(b"trailer", self.data)
        self.assertIn(b"/Root", self.data)

    def test_has_startxref(self):
        self.assertIn(b"startxref", self.data)

    def test_uses_fonts(self):
        self.assertIn(b"/Helvetica", self.data)
        self.assertIn(b"/Helvetica-Bold", self.data)
        self.assertIn(b"/WinAnsiEncoding", self.data)

    def test_object_count_matches_size(self):
        # xref 서브섹션의 객체 수가 trailer 의 /Size 와 일치해야 한다.
        self.assertEqual(_xref_object_count(self.data), _trailer_size(self.data))


class TestPagination(unittest.TestCase):
    def test_single_page(self):
        blocks = [("body", "Short text.")]
        data = minipdf.pdf_bytes(blocks)
        self.assertEqual(_count_page_objects(data), 1)

    def test_multi_page(self):
        # ~200 문단을 넣으면 여러 페이지가 생성되어야 한다.
        blocks = [("body", f"Paragraph number {i} with some content to fill space.")
                  for i in range(200)]
        data = minipdf.pdf_bytes(blocks, title="Big Book")
        n = _count_page_objects(data)
        self.assertGreater(n, 1, f"여러 페이지를 기대했지만 {n} 페이지만 생성됨")

    def test_multi_page_xref_consistent(self):
        blocks = [("body", f"Line {i} content content content.") for i in range(200)]
        data = minipdf.pdf_bytes(blocks)
        self.assertEqual(_xref_object_count(data), _trailer_size(data))

    def test_long_word_wraps(self):
        # 공백 없는 매우 긴 토큰도 깨지지 않고 유효한 PDF 를 만든다.
        blocks = [("body", "x" * 5000)]
        data = minipdf.pdf_bytes(blocks)
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertGreaterEqual(_count_page_objects(data), 1)


class TestXrefOffsets(unittest.TestCase):
    def test_offsets_point_to_objects(self):
        """xref 의 각 오프셋이 실제 'N 0 obj' 위치를 가리키는지 확인."""
        blocks = [("title", "T"), ("body", "Body text here.")]
        data = minipdf.pdf_bytes(blocks)
        m = re.search(rb"xref\s*\n0\s+(\d+)\s*\n", data)
        self.assertIsNotNone(m)
        count = int(m.group(1))
        # 엔트리들 파싱: 첫 줄은 free 객체(0).
        entries_start = m.end()
        entry_re = re.compile(rb"(\d{10}) (\d{5}) ([nf]) ")
        entries = entry_re.findall(data[entries_start:])[:count]
        self.assertEqual(len(entries), count)
        # 객체 1..count-1 (n 엔트리) 의 오프셋이 'obj' 를 가리키는지 검증.
        for i in range(1, count):
            offset, _gen, kind = entries[i]
            if kind == b"f":
                continue
            off = int(offset)
            snippet = data[off:off + 40]
            self.assertRegex(snippet, rb"^%d 0 obj" % i)


class TestWritePdf(unittest.TestCase):
    def test_creates_nonempty_file(self):
        blocks = [("title", "Hello"), ("body", "World paragraph.")]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out", "book.pdf")
            returned = minipdf.write_pdf(blocks, path, title="Title")
            self.assertEqual(returned, path)
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 0)
            with open(path, "rb") as f:
                self.assertEqual(f.read(5), b"%PDF-")

    def test_creates_parent_dirs(self):
        blocks = [("body", "x")]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a", "b", "c", "book.pdf")
            minipdf.write_pdf(blocks, path)
            self.assertTrue(os.path.exists(path))

    def test_korean_input_produces_valid_pdf(self):
        blocks = [("title", "안녕하세요"), ("body", "한국어 본문 텍스트입니다.")]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ko.pdf")
            minipdf.write_pdf(blocks, path)
            with open(path, "rb") as f:
                data = f.read()
            self.assertTrue(data.startswith(b"%PDF-"))
            self.assertIn(b"%%EOF", data)
            # 한국어는 '?' 로 치환되므로 원문 바이트는 없어야 한다.
            self.assertNotIn("안녕".encode("utf-8"), data)

    def test_empty_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "empty.pdf")
            minipdf.write_pdf([], path)
            with open(path, "rb") as f:
                data = f.read()
            self.assertTrue(data.startswith(b"%PDF-"))
            self.assertEqual(_count_page_objects(data), 1)


if __name__ == "__main__":
    unittest.main()
