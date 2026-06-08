"""parser 모듈 단위 테스트."""
import os
import re
import tempfile
import unittest

from ebook_polisher.parser import TextParser, parse_file


MD_SAMPLE = """# 첫 번째 장

## 소제목

이것은 첫 번째 문단입니다.   여기 공백이 많아요.

> 인용문입니다.

# 두 번째 장

두 번째 장의 문단입니다.

### 작은 제목
"""


class TestTextParser(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        )
        self.tmp.write(MD_SAMPLE)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_page_count(self):
        pages = parse_file(self.path)
        # H1이 2개이므로 2페이지여야 한다.
        self.assertEqual(len(pages), 2)

    def test_page_numbers_and_ids(self):
        pages = parse_file(self.path)
        self.assertEqual(pages[0].page_id, "p000001")
        self.assertEqual(pages[1].page_id, "p000002")
        self.assertEqual(pages[0].page_number, 1)
        self.assertEqual(pages[1].page_number, 2)

    def test_page_id_format_and_int_parse(self):
        pages = parse_file(self.path)
        for p in pages:
            self.assertRegex(p.page_id, r"^p\d{6}$")
            # 청커가 의존: int(page_id[1:]) 가 파싱되어야 한다.
            self.assertEqual(int(p.page_id[1:]), p.page_number)

    def test_block_ids_unique_and_padded(self):
        pages = parse_file(self.path)
        all_ids = [b.block_id for p in pages for b in p.blocks]
        self.assertTrue(all(re.match(r"^b\d{6}$", bid) for bid in all_ids))
        self.assertEqual(len(all_ids), len(set(all_ids)), "block_id 중복")
        # 전역 카운터는 1부터 순차.
        self.assertEqual(all_ids[0], "b000001")

    def test_block_page_id_links(self):
        pages = parse_file(self.path)
        for p in pages:
            for b in p.blocks:
                self.assertEqual(b.page_id, p.page_id)

    def test_order_index_sequential(self):
        pages = parse_file(self.path)
        all_blocks = [b for p in pages for b in p.blocks]
        for i, b in enumerate(all_blocks):
            self.assertEqual(b.order_index, i)

    def test_block_types(self):
        pages = parse_file(self.path)
        blocks_by_type = {}
        for p in pages:
            for b in p.blocks:
                blocks_by_type.setdefault(b.block_type, []).append(b)

        # 제목(H1/H2/H3)이 title 로.
        self.assertIn("title", blocks_by_type)
        title_texts = [b.text for b in blocks_by_type["title"]]
        self.assertTrue(any("첫 번째 장" in t for t in title_texts))
        self.assertTrue(any("소제목" in t for t in title_texts))
        self.assertTrue(any("작은 제목" in t for t in title_texts))

        # 인용문.
        self.assertIn("quote", blocks_by_type)
        self.assertTrue(any("인용문" in b.text for b in blocks_by_type["quote"]))

        # 일반 문단.
        self.assertIn("paragraph", blocks_by_type)

    def test_no_empty_block_text(self):
        pages = parse_file(self.path)
        for p in pages:
            for b in p.blocks:
                self.assertTrue(b.text.strip() != "", "빈 블록 발견")

    def test_paragraph_normalized(self):
        pages = parse_file(self.path)
        para = None
        for p in pages:
            for b in p.blocks:
                if b.block_type == "paragraph" and "첫 번째 문단" in b.text:
                    para = b
        self.assertIsNotNone(para)
        # 공백이 축약되어야 한다.
        self.assertNotIn("   ", para.text)

    def test_form_feed_splitting(self):
        content = "첫 페이지 내용\n\n문단2\f두 번째 페이지\n\n또 문단"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name
        try:
            pages = TextParser().parse(path)
            self.assertEqual(len(pages), 2)
            self.assertEqual(pages[0].page_id, "p000001")
            self.assertEqual(pages[1].page_id, "p000002")
        finally:
            os.unlink(path)

    def test_single_page_plain_text(self):
        content = "제목 없는 문단입니다.\n\n또 다른 문단."
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name
        try:
            pages = TextParser().parse(path)
            self.assertEqual(len(pages), 1)
            self.assertEqual(len(pages[0].blocks), 2)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
