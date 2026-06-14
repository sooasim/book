"""상태 원장 + API 팩토리 + 매핑 프리셋 통합 테스트."""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from selenium_bot import status_ledger  # noqa: E402
from selenium_bot.api.factory import api_platform_ids, get_connector, has_api  # noqa: E402
from selenium_bot.field_mapping import MappingStore  # noqa: E402


class TestStatusLedger(unittest.TestCase):
    def test_record_and_upsert(self):
        path = pathlib.Path(tempfile.mkdtemp()) / "results.csv"
        status_ledger.record("z1", "gumroad", "live",
                             platform_url="https://gum.co/x", path=path)
        status_ledger.record("z1", "gumroad", "live", path=path)  # upsert
        status_ledger.record("z1", "amazon_kdp", "in_review", path=path)
        rows = status_ledger.load(path)
        self.assertEqual(len(rows), 2)  # 같은 조합은 한 행
        s = status_ledger.summary(path)
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["by_status"].get("live"), 1)


class TestApiFactory(unittest.TestCase):
    def test_factory_and_dry_run(self):
        self.assertIn("gumroad", api_platform_ids())
        self.assertTrue(has_api("gumroad"))
        self.assertIsNone(get_connector("nope"))
        c = get_connector("gumroad")
        dr = c.dry_run({"title": "제로존", "description": "소개", "price_usd": "9.99"})
        self.assertTrue(dr["ok"])
        self.assertEqual(dr["mode"], "dry_run")
        self.assertEqual(dr["payload"]["price"], 999)  # 센트

    def test_publish_guarded_without_token(self):
        c = get_connector("gumroad", token="")
        res = c.publish({"title": "T"})
        self.assertFalse(res["ok"])
        self.assertIn(res["reason"], ("missing_token", "requests_not_installed"))


class TestMappingPresets(unittest.TestCase):
    def test_presets_load_and_resolve(self):
        store = MappingStore()  # 실제 mappings/ 디렉터리
        for pid in ("amazon_kdp", "bookk_kr", "gumroad", "payhip",
                    "leanpub", "kobo_writing_life", "google_play_books"):
            sel = store.resolve(pid, "title")
            self.assertIsNotNone(sel, f"{pid} title 매핑 누락")
            self.assertIn(sel.by, ("id", "name", "css"))


if __name__ == "__main__":
    unittest.main()
