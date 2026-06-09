"""frontmatter (OCES 03 §6 LAYOUT) 단위 테스트."""
import unittest
from datetime import datetime, timezone

from ebook_polisher.frontmatter import (
    ALLOWED_BLOCK_TYPES,
    STUDIO_CREDIT,
    build_frontmatter,
    copyright_blocks,
    title_page_blocks,
    toc_blocks,
)


def _texts(blocks):
    return [t for _, t in blocks]


def _types(blocks):
    return [bt for bt, _ in blocks]


class TitlePageTests(unittest.TestCase):
    def test_includes_title_as_first_title_block(self):
        blocks = title_page_blocks("나의 책")
        self.assertEqual(blocks[0], ("title", "나의 책"))

    def test_author_line_only_when_given(self):
        with_author = title_page_blocks("T", author="홍길동")
        self.assertIn(("paragraph", "지은이: 홍길동"), with_author)
        without_author = title_page_blocks("T")
        self.assertFalse(
            any(t.startswith("지은이") for t in _texts(without_author))
        )

    def test_subtitle_handling(self):
        with_sub = title_page_blocks("T", subtitle="부제")
        self.assertIn(("paragraph", "부제"), with_sub)
        without_sub = title_page_blocks("T")
        self.assertNotIn(("paragraph", ""), without_sub)
        self.assertEqual(len(without_sub), 1)

    def test_full_order(self):
        blocks = title_page_blocks("T", author="A", subtitle="S")
        self.assertEqual(
            blocks,
            [("title", "T"), ("paragraph", "S"), ("paragraph", "지은이: A")],
        )

    def test_all_types_allowed(self):
        blocks = title_page_blocks("T", author="A", subtitle="S")
        for bt in _types(blocks):
            self.assertIn(bt, ALLOWED_BLOCK_TYPES)


class CopyrightTests(unittest.TestCase):
    def test_has_pankwon_title(self):
        blocks = copyright_blocks("T", author="A", year=2020)
        self.assertEqual(blocks[0], ("title", "판권"))

    def test_contains_year_author_and_credit(self):
        blocks = copyright_blocks("T", author="홍길동", year=1999)
        texts = _texts(blocks)
        self.assertTrue(any("1999" in t for t in texts))
        self.assertTrue(any("홍길동" in t for t in texts))
        self.assertIn(STUDIO_CREDIT, texts)

    def test_year_defaults_to_current_utc_year(self):
        blocks = copyright_blocks("T", author="A")
        expected = datetime.now(timezone.utc).year
        texts = _texts(blocks)
        self.assertTrue(
            any(str(expected) in t for t in texts),
            f"current year {expected} not found in {texts}",
        )

    def test_isbn_line_only_when_given(self):
        with_isbn = copyright_blocks("T", isbn="978-0-00-000000-0")
        self.assertTrue(
            any("978-0-00-000000-0" in t for t in _texts(with_isbn))
        )
        without_isbn = copyright_blocks("T")
        self.assertFalse(any("ISBN" in t for t in _texts(without_isbn)))

    def test_publisher_line_only_when_given(self):
        with_pub = copyright_blocks("T", publisher="원클릭출판")
        self.assertTrue(any("원클릭출판" in t for t in _texts(with_pub)))
        without_pub = copyright_blocks("T")
        self.assertFalse(any("발행처" in t for t in _texts(without_pub)))

    def test_contains_book_title(self):
        blocks = copyright_blocks("멋진제목", author="A", year=2020)
        self.assertIn("멋진제목", _texts(blocks))

    def test_all_types_allowed(self):
        blocks = copyright_blocks(
            "T", author="A", year=2020, publisher="P", isbn="X"
        )
        for bt in _types(blocks):
            self.assertIn(bt, ALLOWED_BLOCK_TYPES)


class TocTests(unittest.TestCase):
    def test_empty_returns_empty(self):
        self.assertEqual(toc_blocks([]), [])

    def test_n_chapters_numbered(self):
        chapters = [
            {"title": "서론"},
            {"title": "본론"},
            {"title": "결론"},
        ]
        blocks = toc_blocks(chapters)
        self.assertEqual(blocks[0], ("title", "목차"))
        self.assertEqual(len(blocks), 4)
        self.assertEqual(blocks[1], ("paragraph", "1. 서론"))
        self.assertEqual(blocks[2], ("paragraph", "2. 본론"))
        self.assertEqual(blocks[3], ("paragraph", "3. 결론"))

    def test_numbering_starts_at_one(self):
        chapters = [{"title": f"장{i}"} for i in range(5)]
        blocks = toc_blocks(chapters)
        paras = _texts(blocks[1:])
        self.assertTrue(paras[0].startswith("1."))
        self.assertTrue(paras[-1].startswith("5."))

    def test_optional_idx_ignored_for_numbering(self):
        chapters = [{"title": "A", "idx": 99}, {"title": "B", "idx": 7}]
        blocks = toc_blocks(chapters)
        self.assertEqual(blocks[1], ("paragraph", "1. A"))
        self.assertEqual(blocks[2], ("paragraph", "2. B"))

    def test_all_types_allowed(self):
        blocks = toc_blocks([{"title": "A"}, {"title": "B"}])
        for bt in _types(blocks):
            self.assertIn(bt, ALLOWED_BLOCK_TYPES)


class BuildFrontmatterTests(unittest.TestCase):
    def _meta(self):
        return {
            "title": "책 제목",
            "author": "지은이",
            "subtitle": "부제",
            "year": 2021,
            "publisher": "출판사",
            "isbn": "978-1",
        }

    def _chapters(self):
        return [{"title": "1장"}, {"title": "2장"}]

    def test_returns_valid_tuples(self):
        blocks = build_frontmatter(self._meta(), self._chapters())
        self.assertIsInstance(blocks, list)
        for b in blocks:
            self.assertIsInstance(b, tuple)
            self.assertEqual(len(b), 2)
            bt, text = b
            self.assertIsInstance(bt, str)
            self.assertIsInstance(text, str)

    def test_first_block_is_title(self):
        blocks = build_frontmatter(self._meta(), self._chapters())
        self.assertEqual(blocks[0][0], "title")

    def test_contains_pankwon_and_mokcha_titles(self):
        blocks = build_frontmatter(self._meta(), self._chapters())
        title_texts = [t for bt, t in blocks if bt == "title"]
        self.assertIn("판권", title_texts)
        self.assertIn("목차", title_texts)

    def test_all_block_types_allowed(self):
        blocks = build_frontmatter(self._meta(), self._chapters())
        for bt in _types(blocks):
            self.assertIn(bt, ALLOWED_BLOCK_TYPES)

    def test_deterministic(self):
        meta, chapters = self._meta(), self._chapters()
        self.assertEqual(
            build_frontmatter(meta, chapters),
            build_frontmatter(meta, chapters),
        )

    def test_composition_order_title_then_copyright_then_toc(self):
        blocks = build_frontmatter(self._meta(), self._chapters())
        title_indices = [i for i, (bt, _) in enumerate(blocks) if bt == "title"]
        # 표제지 title, 판권 title, 목차 title 순서.
        self.assertEqual(blocks[title_indices[0]][1], "책 제목")
        self.assertEqual(blocks[title_indices[1]][1], "판권")
        self.assertEqual(blocks[title_indices[2]][1], "목차")

    def test_no_chapters_omits_toc(self):
        blocks = build_frontmatter(self._meta(), [])
        self.assertNotIn("목차", [t for bt, t in blocks if bt == "title"])

    def test_minimal_meta(self):
        blocks = build_frontmatter({"title": "T"}, [])
        self.assertEqual(blocks[0], ("title", "T"))
        title_texts = [t for bt, t in blocks if bt == "title"]
        self.assertIn("판권", title_texts)


if __name__ == "__main__":
    unittest.main()
