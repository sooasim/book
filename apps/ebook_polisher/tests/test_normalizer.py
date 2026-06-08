"""normalizer 모듈 단위 테스트."""
import unicodedata
import unittest

from ebook_polisher.normalizer import normalize_text, strip_invisible


class TestNormalizer(unittest.TestCase):
    def test_idempotency(self):
        samples = [
            "hello   world\t\t\n\n\n\nbye   ",
            "한글  텍스트\n\n\n\n\n다음",
            "  spaced  lines  \n  more  ",
            "",
        ]
        for s in samples:
            once = normalize_text(s)
            twice = normalize_text(once)
            self.assertEqual(once, twice, f"not idempotent for: {s!r}")

    def test_space_collapsing(self):
        self.assertEqual(normalize_text("a    b"), "a b")
        self.assertEqual(normalize_text("a\tb"), "a b")
        self.assertEqual(normalize_text("a \t  b"), "a b")

    def test_trailing_space_stripped(self):
        self.assertEqual(normalize_text("a   \nb  "), "a\nb")

    def test_blank_line_collapse(self):
        # "a" + 4개의 빈 줄 + "b" => 빈 줄 최대 2개로 축약.
        # 결과 문자열: "a" \n (빈 줄) \n (빈 줄) \n "b" = "a\n\n\nb"
        out = normalize_text("a\n\n\n\n\nb")
        self.assertEqual(out, "a\n\n\nb")
        # 이미 2개 이하면 유지.
        self.assertEqual(normalize_text("a\n\nb"), "a\n\nb")
        self.assertEqual(normalize_text("a\nb"), "a\nb")

    def test_nfc(self):
        # 분해형(NFD) 한글이 NFC로 합쳐져야 한다.
        decomposed = unicodedata.normalize("NFD", "한글")
        self.assertNotEqual(decomposed, "한글")  # 사전 조건
        self.assertEqual(normalize_text(decomposed), "한글")

    def test_zero_width_removal(self):
        zw = "a​b‌‍⁠﻿c"
        self.assertEqual(normalize_text(zw), "abc")
        self.assertEqual(strip_invisible(zw), "abc")

    def test_digits_preserved(self):
        s = "가격 1,234.50 원 (ISBN 978-89-12345-67-8)"
        self.assertEqual(normalize_text(s), s)

    def test_letters_punct_preserved(self):
        s = "Hello, World! 안녕하세요? — 끝."
        self.assertEqual(normalize_text(s), s)

    def test_empty(self):
        self.assertEqual(normalize_text(""), "")


if __name__ == "__main__":
    unittest.main()
