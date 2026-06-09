"""cover 모듈 테스트 — 표준 라이브러리만으로 결정적 SVG 표지 검증."""
import tempfile
import unittest
from pathlib import Path
from xml.dom import minidom

from ebook_polisher import cover


class TestCoverSvgBasic(unittest.TestCase):
    def test_returns_xml_string(self):
        svg = cover.cover_svg("My Book", author="Jane Doe")
        self.assertIsInstance(svg, str)
        self.assertTrue(svg.startswith("<?xml") or svg.startswith("<svg"))

    def test_well_formed_xml(self):
        svg = cover.cover_svg("My Book", author="Jane Doe", subtitle="A Tale")
        # 파싱 실패 시 예외가 발생하므로 well-formed 검증이 된다.
        doc = minidom.parseString(svg)
        self.assertEqual(doc.documentElement.tagName, "svg")
        self.assertTrue(doc.documentElement.getAttribute("xmlns"))


class TestDeterminism(unittest.TestCase):
    def test_same_inputs_identical(self):
        a = cover.cover_svg("Same Title", author="A", subtitle="S")
        b = cover.cover_svg("Same Title", author="A", subtitle="S")
        self.assertEqual(a, b)

    def test_different_titles_differ(self):
        a = cover.cover_svg("Title One")
        b = cover.cover_svg("Title Two")
        self.assertNotEqual(a, b)

    def test_color_derived_from_title(self):
        # 다른 제목은 (보통) 다른 배경색을 가진다.
        a = cover.cover_svg("Alpha")
        b = cover.cover_svg("Beta")
        self.assertNotEqual(a, b)


class TestXmlEscaping(unittest.TestCase):
    def test_special_chars_escaped_and_parseable(self):
        title = 'Tom & Jerry <best> "buddies"'
        svg = cover.cover_svg(title, author="A & B")
        # 파싱 가능해야 한다.
        minidom.parseString(svg)
        # 원시 위험 문자가 그대로 노출되면 안 된다.
        self.assertIn("&amp;", svg)
        self.assertIn("&lt;", svg)
        self.assertIn("&quot;", svg)
        # 이스케이프 안 된 < 로 인한 가짜 태그가 없어야 함.
        self.assertNotIn("<best>", svg)

    def test_apostrophe_escaped(self):
        svg = cover.cover_svg("It's Mine")
        minidom.parseString(svg)
        self.assertIn("&apos;", svg)


class TestLongTitle(unittest.TestCase):
    def test_long_title_well_formed(self):
        title = "A" * 60
        svg = cover.cover_svg(title, author="Author Name")
        doc = minidom.parseString(svg)
        # 여러 tspan 으로 줄바꿈되었는지 확인.
        tspans = doc.getElementsByTagName("tspan")
        self.assertGreater(len(tspans), 1)

    def test_long_title_ellipsis(self):
        title = "word " * 40  # 매우 긴 제목 → 줄 수 초과 → 말줄임.
        svg = cover.cover_svg(title)
        minidom.parseString(svg)
        self.assertIn("…", svg)

    def test_author_present(self):
        svg = cover.cover_svg("Short", author="Specific Author")
        self.assertIn("Specific Author", svg)

    def test_cjk_title_wraps(self):
        title = "동해물과백두산이마르고닳도록하느님이보우하사우리나라만세"
        svg = cover.cover_svg(title)
        doc = minidom.parseString(svg)
        self.assertGreater(len(doc.getElementsByTagName("tspan")), 1)


class TestEmptyAndOptional(unittest.TestCase):
    def test_no_author_no_subtitle(self):
        svg = cover.cover_svg("Just Title")
        minidom.parseString(svg)

    def test_empty_title(self):
        svg = cover.cover_svg("")
        minidom.parseString(svg)


class TestWriteCoverSvg(unittest.TestCase):
    def test_creates_nonempty_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "nested" / "cover.svg")
            ret = cover.write_cover_svg(path, "Book", author="Auth")
            self.assertEqual(ret, path)
            self.assertTrue(Path(path).exists())
            self.assertGreater(Path(path).stat().st_size, 0)


class TestSvgToPng(unittest.TestCase):
    def test_missing_cairosvg_raises(self):
        try:
            import cairosvg  # noqa: F401
            has = True
        except Exception:
            has = False
        if has:
            self.skipTest("cairosvg 설치됨 — 결측 동작 테스트 불가")
        with self.assertRaises(RuntimeError):
            cover.svg_to_png("<svg/>", "/tmp/out.png")


if __name__ == "__main__":
    unittest.main()
