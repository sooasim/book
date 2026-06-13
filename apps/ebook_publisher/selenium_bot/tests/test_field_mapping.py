"""field_mapping.py 매핑 저장소 테스트."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from selenium_bot import field_mapping
from selenium_bot.field_mapping import DEFAULT_FIELD_KEYS, MappingStore, coverage, seed_example
from selenium_bot.models import FieldSelector


class TestMappingStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = MappingStore(mappings_dir=self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_path_for(self):
        path = self.store.path_for("amazon_kdp")
        self.assertEqual(path.name, "amazon_kdp.json")
        self.assertEqual(path.parent, pathlib.Path(self._tmp.name))

    def test_load_unknown_platform_empty(self):
        self.assertEqual(self.store.load("does_not_exist"), {})

    def test_resolve_unknown_returns_none(self):
        self.assertIsNone(self.store.resolve("missing", "title"))

    def test_set_field_then_resolve(self):
        self.store.set_field("kobo", "title", "css", "#title", "text")
        sel = self.store.resolve("kobo", "title")
        self.assertIsInstance(sel, FieldSelector)
        self.assertEqual(sel.field_key, "title")
        self.assertEqual(sel.by, "css")
        self.assertEqual(sel.selector, "#title")
        self.assertEqual(sel.field_type, "text")

    def test_set_field_default_field_type(self):
        self.store.set_field("kobo", "author", "name", "author")
        sel = self.store.resolve("kobo", "author")
        self.assertEqual(sel.field_type, "text")

    def test_set_field_updates_existing(self):
        self.store.set_field("kobo", "title", "css", "#title", "text")
        self.store.set_field("kobo", "title", "name", "title_field", "text")
        sel = self.store.resolve("kobo", "title")
        self.assertEqual(sel.by, "name")
        self.assertEqual(sel.selector, "title_field")

    def test_save_returns_path(self):
        path = self.store.save(
            "kobo", {"title": FieldSelector("title", "css", "#title", "text")}
        )
        self.assertTrue(str(path).endswith("kobo.json"))

    def test_save_load_roundtrip(self):
        selectors = {
            "title": FieldSelector("title", "css", "#title", "text"),
            "cover_file": FieldSelector("cover_file", "css", "#cover", "file"),
            "description": FieldSelector("description", "xpath", "//textarea", "textarea"),
        }
        self.store.save("kobo", selectors)
        loaded = self.store.load("kobo")
        self.assertEqual(set(loaded.keys()), set(selectors.keys()))
        for key, original in selectors.items():
            self.assertEqual(loaded[key], original)


class TestCoverage(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = MappingStore(mappings_dir=self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_platform_all_missing(self):
        cov = coverage("empty", self.store)
        self.assertEqual(cov["known"], [])
        self.assertEqual(set(cov["missing"]), set(DEFAULT_FIELD_KEYS))

    def test_reports_known_and_missing(self):
        self.store.set_field("kobo", "title", "css", "#title")
        self.store.set_field("kobo", "price", "name", "price")
        cov = coverage("kobo", self.store)
        self.assertIn("title", cov["known"])
        self.assertIn("price", cov["known"])
        self.assertNotIn("title", cov["missing"])
        self.assertNotIn("price", cov["missing"])
        self.assertIn("isbn", cov["missing"])


class TestSeedExample(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = MappingStore(mappings_dir=self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_seed_populates_amazon_kdp(self):
        path = seed_example(self.store)
        self.assertTrue(str(path).endswith("amazon_kdp.json"))
        sel = self.store.resolve("amazon_kdp", "title")
        self.assertIsNotNone(sel)
        self.assertIsInstance(sel, FieldSelector)

    def test_seed_uses_generic_title_selector(self):
        seed_example(self.store)
        sel = self.store.resolve("amazon_kdp", "title")
        self.assertEqual(sel.by, "name")
        self.assertEqual(sel.selector, "title")


class TestModuleConstants(unittest.TestCase):
    def test_mappings_dir_is_path(self):
        self.assertTrue(str(field_mapping.MAPPINGS_DIR).endswith("mappings"))

    def test_default_field_keys(self):
        self.assertIn("title", DEFAULT_FIELD_KEYS)
        self.assertIn("isbn", DEFAULT_FIELD_KEYS)


if __name__ == "__main__":
    unittest.main()
