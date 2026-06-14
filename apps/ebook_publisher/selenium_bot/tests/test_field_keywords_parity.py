"""파리티 테스트: field_keywords.json(단일 소스) == inspector.FIELD_KEYWORDS,
그리고 크롬 확장에 동봉된 복사본이 동일해야 한다(휴리스틱 동기화 강제)."""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from selenium_bot.inspector import FIELD_KEYWORDS, FILE_FIELD_KEYS  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[4]   # .../book
RES = REPO / "resources" / "field_keywords.json"
EXT = REPO / "apps" / "ebook_publisher" / "chrome_extension" / "field_keywords.json"


class TestParity(unittest.TestCase):
    def test_resource_matches_inspector(self):
        doc = json.loads(RES.read_text(encoding="utf-8"))
        self.assertEqual(doc["fields"], {k: list(v) for k, v in FIELD_KEYWORDS.items()})
        self.assertEqual(doc["file_fields"], list(FILE_FIELD_KEYS))
        self.assertTrue(len(doc["sensitive"]) >= 10)
        # 민감어에 핵심 항목 포함
        for must in ("password", "비밀번호", "captcha", "사업자", "계좌", "세금"):
            self.assertIn(must, doc["sensitive"])

    def test_extension_copy_matches_resource(self):
        self.assertTrue(EXT.exists(), "확장 동봉 field_keywords.json 누락")
        self.assertEqual(json.loads(EXT.read_text(encoding="utf-8")),
                         json.loads(RES.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
