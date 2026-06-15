"""스튜디오 → 확장 기본정보 내보내기 테스트."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import service  # noqa: E402


class TestExtensionProfile(unittest.TestCase):
    def setUp(self):
        service.reset_store()

    def test_export_shape_after_compose(self):
        p = service.create_project("제로존 입문", topic="제로존 수학과 존재론",
                                   n_chapters=3, author="ATA")
        service.compose_project(p["project_id"])
        prof = service.export_extension_profile(p["project_id"])
        self.assertEqual(prof["title"], "제로존 입문")
        self.assertEqual(prof["author"], "ATA")
        self.assertEqual(prof["language"], "ko")
        self.assertEqual(prof["short_description"], "제로존 수학과 존재론")
        self.assertTrue(len(prof["description"]) > 0)         # 윤문본에서 추출
        self.assertNotIn("#", prof["description"])            # 헤딩 제외
        # 확장 허용 키만 포함
        for k in prof:
            self.assertIn(k, ("title", "subtitle", "author", "pen_name", "language",
                              "short_description", "description", "keywords",
                              "categories", "price_krw", "price_usd", "isbn_ebook"))

    def test_export_unknown_project(self):
        self.assertIsNone(service.export_extension_profile("nope"))


if __name__ == "__main__":
    unittest.main()
