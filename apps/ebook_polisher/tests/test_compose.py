"""compose.py 테스트 (OCES Outline + Write). StubProvider로 결정적 검증."""
import unittest

from ebook_polisher.compose import (
    Outline,
    OutlineChapter,
    build_outline,
    compose_to_markdown,
    write_book,
)
from ebook_polisher.llm_provider import StubProvider


class TestBuildOutline(unittest.TestCase):
    def setUp(self):
        self.length = 6000
        self.outline = build_outline(
            "테스트 책", "강화학습", n_chapters=6, length_target=self.length
        )

    def test_chapter_count(self):
        self.assertEqual(len(self.outline.chapters), 6)

    def test_unique_titles(self):
        titles = [c.title for c in self.outline.chapters]
        self.assertEqual(len(titles), len(set(titles)))

    def test_first_is_intro(self):
        self.assertIn("서론", self.outline.chapters[0].title)

    def test_last_is_conclusion(self):
        self.assertIn("결론", self.outline.chapters[-1].title)

    def test_briefs_nonempty(self):
        for c in self.outline.chapters:
            self.assertTrue(c.brief.strip(), f"브리프 비어있음: {c.title}")

    def test_word_budget_within_5pct(self):
        total = sum(c.target_words for c in self.outline.chapters)
        self.assertLessEqual(abs(total - self.length), self.length * 0.05)

    def test_clamp_min_chapters(self):
        outline = build_outline("작은 책", "주제", n_chapters=1)
        self.assertGreaterEqual(len(outline.chapters), 3)


class TestWriteBook(unittest.TestCase):
    def _fresh_outline(self):
        return build_outline("일관성 책", "양자컴퓨팅", n_chapters=5, length_target=5000)

    def test_all_content_nonempty(self):
        outline = write_book(self._fresh_outline(), StubProvider())
        for c in outline.chapters:
            self.assertTrue(c.content_md.strip(), f"본문 비어있음: {c.title}")

    def test_carryover_visible(self):
        outline = write_book(self._fresh_outline(), StubProvider())
        # 2번째 챕터부터는 CARRY가 비어있지 않으므로 StubProvider가 "앞 장에서" 문구를 포함
        self.assertIn("앞 장에서", outline.chapters[1].content_md)

    def test_first_chapter_no_carryover(self):
        outline = write_book(self._fresh_outline(), StubProvider())
        # 첫 챕터는 CARRY가 비어 캐리오버 문구가 없어야 한다
        self.assertNotIn("앞 장에서", outline.chapters[0].content_md)

    def test_deterministic(self):
        a = write_book(self._fresh_outline(), StubProvider())
        b = write_book(self._fresh_outline(), StubProvider())
        self.assertEqual(
            [c.content_md for c in a.chapters],
            [c.content_md for c in b.chapters],
        )

    def test_summaries_set(self):
        outline = write_book(self._fresh_outline(), StubProvider())
        for c in outline.chapters:
            self.assertTrue(c.summary.strip())


class TestComposeToMarkdown(unittest.TestCase):
    def test_starts_with_title(self):
        md = compose_to_markdown("나의 책", "딥러닝")
        self.assertTrue(md.startswith("# 나의 책"))

    def test_contains_all_chapter_headers(self):
        outline = build_outline("나의 책", "딥러닝", n_chapters=6)
        md = compose_to_markdown("나의 책", "딥러닝", n_chapters=6)
        for c in outline.chapters:
            self.assertIn(f"## {c.title}", md)

    def test_contains_topic(self):
        md = compose_to_markdown("나의 책", "딥러닝")
        self.assertIn("딥러닝", md)

    def test_deterministic(self):
        a = compose_to_markdown("나의 책", "딥러닝")
        b = compose_to_markdown("나의 책", "딥러닝")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
