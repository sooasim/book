"""신규 모듈 테스트: profile_store(기본정보 1회), inspector(구조 파악), batch(일괄)."""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from selenium_bot import batch, inspector, profile_store  # noqa: E402
from selenium_bot.field_mapping import MappingStore  # noqa: E402
from selenium_bot.registry import load_registry  # noqa: E402


class TestProfileStore(unittest.TestCase):
    def test_book_profile_roundtrip(self):
        base = tempfile.mkdtemp()
        profile_store.save_book_profile(
            {"book_id": "z1", "title": "제로존", "price_usd": "9.99", "secret": "x"}, base)
        loaded = profile_store.load_book_profile(base)
        self.assertEqual(loaded["title"], "제로존")
        self.assertNotIn("secret", loaded)  # 화이트리스트 필드만 저장

    def test_publisher_profile_roundtrip(self):
        base = tempfile.mkdtemp()
        profile_store.save_publisher_profile({"display_name": "ATA", "email": "a@b.c"}, base)
        self.assertEqual(profile_store.load_publisher_profile(base)["display_name"], "ATA")

    def test_profile_dir_persistent_session(self):
        base = tempfile.mkdtemp()
        self.assertFalse(profile_store.is_logged_in("amazon_kdp", base))
        d = profile_store.profile_dir_for("amazon_kdp", base)
        (pathlib.Path(d) / "Default").mkdir()  # 로그인 후 생성될 법한 흔적
        self.assertTrue(profile_store.is_logged_in("amazon_kdp", base))


class TestInspector(unittest.TestCase):
    def test_guess_field_key_en_ko(self):
        self.assertEqual(inspector.guess_field_key({"tag": "input", "name": "title"}), "title")
        self.assertEqual(inspector.guess_field_key({"tag": "input", "placeholder": "제목"}), "title")
        self.assertEqual(inspector.guess_field_key(
            {"tag": "textarea", "id": "book_description", "label": "책소개"}), "description")
        self.assertEqual(inspector.guess_field_key({"tag": "input", "name": "가격"}), "price")
        self.assertEqual(inspector.guess_field_key(
            {"tag": "input", "type": "file", "name": "cover-image"}), "cover_file")
        self.assertIsNone(inspector.guess_field_key({"tag": "input", "name": "xyzzy"}))

    def test_propose_mapping_prefers_id(self):
        desc = [
            {"tag": "input", "type": "text", "id": "title", "name": "t"},
            {"tag": "textarea", "id": "desc", "placeholder": "설명"},
            {"tag": "input", "type": "file", "name": "manuscript", "id": "ms"},
        ]
        m = inspector.propose_mapping(desc)
        self.assertEqual(m["title"].by, "id")
        self.assertEqual(m["title"].selector, "title")
        self.assertEqual(m["manuscript_file"].field_type, "file")

    def test_learn_mapping_with_fake_driver(self):
        class FakeEl:
            def __init__(self, attrs): self._a = attrs
            def get_attribute(self, k):
                return self._a.get(k.replace("-", "_"))
        class FakeDriver:
            def find_elements(self, by, tag):
                if tag == "input":
                    return [FakeEl({"type": "text", "id": "title", "name": "title"}),
                            FakeEl({"type": "file", "name": "cover", "id": "cover"})]
                if tag == "textarea":
                    return [FakeEl({"id": "description", "placeholder": "책소개"})]
                return []
        store = MappingStore(tempfile.mkdtemp())
        rep = inspector.learn_mapping("demo", FakeDriver(), store)
        self.assertIn("title", rep["mapped"])
        self.assertIn("description", rep["mapped"])
        self.assertIsNotNone(store.resolve("demo", "title"))


class TestBatch(unittest.TestCase):
    def test_prepare_all_covers_all_sites(self):
        sites = load_registry()
        book = {"book_id": "z1", "title": "제로존", "author": "ATA",
                "description": "소개", "price_usd": "9.99", "language": "ko"}
        plans = batch.prepare_all(book, sites, {"epub": "/tmp/x.epub"})
        self.assertEqual(len(plans), len(sites))
        # 각 계획의 마지막은 final_submit 게이트
        for plan in plans.values():
            self.assertEqual(plan.steps[-1].gate, "final_submit")
        s = batch.summary(plans)
        self.assertEqual(s["platforms"], len(sites))

    def test_signup_all(self):
        sites = load_registry()
        plans = batch.signup_all({"display_name": "ATA", "email": "a@b.c"}, sites)
        self.assertEqual(len(plans), len(sites))

    def test_write_manifest(self):
        sites = load_registry()[:3]
        book = {"book_id": "z1", "title": "T", "description": "d", "price_usd": "1"}
        plans = batch.prepare_all(book, sites)
        out = tempfile.mkdtemp()
        m = batch.write_manifest(plans, out)
        self.assertTrue(pathlib.Path(m).exists())


if __name__ == "__main__":
    unittest.main()
