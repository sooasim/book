"""공식 API 커넥터 레이어 테스트. 네트워크/토큰 없이 표준 라이브러리만 사용."""
from __future__ import annotations

import sys
import pathlib
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from selenium_bot.api.factory import get_connector, api_platform_ids, has_api
from selenium_bot.api.gumroad import GumroadConnector
from selenium_bot.api.leanpub import LeanpubConnector
from selenium_bot.api.publishdrive import PublishDriveConnector


SAMPLE_BOOK = {
    "title": "My Test Book",
    "subtitle": "A Subtitle",
    "description": "A description.",
    "price_usd": "9.99",
    "language": "en",
    "isbn_ebook": "978-1-23-456789-0",
    "url": "my-test-book",
}


class TestFactory(unittest.TestCase):
    def test_get_connector_gumroad(self):
        c = get_connector("gumroad")
        self.assertIsInstance(c, GumroadConnector)

    def test_get_connector_leanpub(self):
        self.assertIsInstance(get_connector("leanpub"), LeanpubConnector)

    def test_get_connector_publishdrive(self):
        self.assertIsInstance(get_connector("publishdrive"), PublishDriveConnector)

    def test_get_connector_unknown(self):
        self.assertIsNone(get_connector("kdp"))
        self.assertIsNone(get_connector("does-not-exist"))

    def test_api_platform_ids(self):
        ids = api_platform_ids()
        self.assertIn("gumroad", ids)
        self.assertIn("leanpub", ids)
        self.assertIn("publishdrive", ids)

    def test_has_api(self):
        self.assertTrue(has_api("gumroad"))
        self.assertFalse(has_api("kdp"))

    def test_token_passthrough(self):
        c = get_connector("gumroad", token="abc123")
        self.assertEqual(c.token, "abc123")


class TestGumroadPayload(unittest.TestCase):
    def test_price_to_cents(self):
        c = GumroadConnector()
        payload = c.build_payload(SAMPLE_BOOK)
        self.assertEqual(payload["price"], 999)

    def test_name_equals_title(self):
        c = GumroadConnector()
        payload = c.build_payload(SAMPLE_BOOK)
        self.assertEqual(payload["name"], "My Test Book")

    def test_keys(self):
        c = GumroadConnector()
        payload = c.build_payload(SAMPLE_BOOK)
        self.assertEqual(set(payload.keys()), {"name", "description", "price", "url"})

    def test_missing_price_defaults_zero(self):
        c = GumroadConnector()
        payload = c.build_payload({"title": "x"})
        self.assertEqual(payload["price"], 0)

    def test_deterministic(self):
        c = GumroadConnector()
        self.assertEqual(c.build_payload(SAMPLE_BOOK), c.build_payload(SAMPLE_BOOK))


class TestLeanpubPayload(unittest.TestCase):
    def test_keys(self):
        c = LeanpubConnector()
        payload = c.build_payload(SAMPLE_BOOK)
        self.assertEqual(set(payload.keys()), {"title", "subtitle", "about_the_book"})
        self.assertEqual(payload["about_the_book"], "A description.")
        self.assertEqual(payload["title"], "My Test Book")


class TestPublishDrivePayload(unittest.TestCase):
    def test_keys(self):
        c = PublishDriveConnector()
        payload = c.build_payload(SAMPLE_BOOK)
        self.assertEqual(
            set(payload.keys()),
            {"title", "description", "isbn", "language", "price_usd"},
        )
        self.assertEqual(payload["isbn"], "978-1-23-456789-0")


class TestDryRun(unittest.TestCase):
    def test_gumroad_dry_run(self):
        c = GumroadConnector()
        res = c.dry_run(SAMPLE_BOOK)
        self.assertTrue(res["ok"])
        self.assertEqual(res["mode"], "dry_run")
        self.assertEqual(res["platform"], "gumroad")
        self.assertEqual(res["endpoint"], "https://api.gumroad.com/v2/products")
        self.assertEqual(res["payload"]["price"], 999)

    def test_leanpub_dry_run(self):
        res = LeanpubConnector().dry_run(SAMPLE_BOOK)
        self.assertTrue(res["ok"])
        self.assertEqual(res["endpoint"], "https://leanpub.com/api")

    def test_publishdrive_dry_run(self):
        res = PublishDriveConnector().dry_run(SAMPLE_BOOK)
        self.assertTrue(res["ok"])
        self.assertEqual(res["endpoint"], "https://api.publishdrive.com/v1/books")

    def test_dry_run_deterministic(self):
        c = GumroadConnector()
        self.assertEqual(c.dry_run(SAMPLE_BOOK), c.dry_run(SAMPLE_BOOK))


class TestPublishGuards(unittest.TestCase):
    def test_publish_without_token(self):
        c = GumroadConnector(token="")
        res = c.publish(SAMPLE_BOOK)
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "missing_token")
        self.assertEqual(res["token_env"], "GUMROAD_ACCESS_TOKEN")

    def test_publish_all_connectors_without_token(self):
        for pid in api_platform_ids():
            c = get_connector(pid, token="")
            res = c.publish(SAMPLE_BOOK)
            self.assertFalse(res["ok"])
            self.assertEqual(res["reason"], "missing_token")


class TestHumanReviewNote(unittest.TestCase):
    def test_note_nonempty(self):
        self.assertTrue(GumroadConnector().human_review_note())


if __name__ == "__main__":
    unittest.main()
