"""registry.py 단위 테스트 — Selenium/네트워크 없음."""
import pathlib
import sys
import unittest

# 테스트는 CWD == selenium_bot 에서 돌아간다. 패키지 루트(selenium_bot)의
# 부모(apps/ebook_publisher)를 sys.path 에 넣어 `selenium_bot.*` 절대 임포트가 되게 한다.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from selenium_bot.models import HUMAN_GATES, PlatformSite  # noqa: E402
from selenium_bot.registry import (  # noqa: E402
    DEFAULT_REGISTRY_PATH,
    automation_levels,
    filter_sites,
    get_site,
    load_registry,
    regions,
    validate_registry,
)


class LoadRegistryTests(unittest.TestCase):
    def setUp(self):
        self.sites = load_registry()

    def test_default_path_points_to_csv(self):
        self.assertTrue(str(DEFAULT_REGISTRY_PATH).endswith("platform_registry_global.csv"))
        self.assertTrue(DEFAULT_REGISTRY_PATH.exists())

    def test_returns_platform_site_objects(self):
        self.assertTrue(self.sites)
        self.assertIsInstance(self.sites[0], PlatformSite)

    def test_at_least_40_sites(self):
        self.assertGreaterEqual(len(self.sites), 40)

    def test_amazon_kdp_fields(self):
        site = get_site(self.sites, "amazon_kdp")
        self.assertIsNotNone(site)
        self.assertEqual(site.region, "global")
        self.assertIn("final_submit", site.human_gates)

    def test_api_available_is_bool(self):
        for site in self.sites:
            self.assertIsInstance(site.api_available, bool)
        # CSV 에 'true' 와 'false' 가 모두 있으므로 두 값 다 나타나야 한다.
        bools = {site.api_available for site in self.sites}
        self.assertEqual(bools, {True, False})

    def test_human_gates_is_clean_list(self):
        for site in self.sites:
            self.assertIsInstance(site.human_gates, list)
            for gate in site.human_gates:
                self.assertEqual(gate, gate.strip())
                self.assertNotEqual(gate, "")

    def test_load_with_explicit_path(self):
        sites = load_registry(DEFAULT_REGISTRY_PATH)
        self.assertEqual(len(sites), len(self.sites))


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.sites = load_registry()

    def test_filter_region_kr(self):
        kr = filter_sites(self.sites, region="kr")
        self.assertTrue(kr)
        self.assertTrue(all(s.region == "kr" for s in kr))

    def test_filter_automation_level(self):
        api = filter_sites(self.sites, automation_level="api")
        self.assertTrue(all(s.automation_level == "api" for s in api))

    def test_filter_entry_type(self):
        comm = filter_sites(self.sites, entry_type="community")
        self.assertTrue(comm)
        self.assertTrue(all(s.entry_type == "community" for s in comm))

    def test_api_only(self):
        api_only = filter_sites(self.sites, api_only=True)
        self.assertTrue(api_only)
        self.assertTrue(all(s.api_available for s in api_only))
        self.assertLess(len(api_only), len(self.sites))

    def test_combined_filters_and(self):
        combined = filter_sites(self.sites, region="global", api_only=True)
        self.assertTrue(all(s.region == "global" and s.api_available for s in combined))

    def test_no_filter_returns_all(self):
        self.assertEqual(len(filter_sites(self.sites)), len(self.sites))


class LookupAndCountTests(unittest.TestCase):
    def setUp(self):
        self.sites = load_registry()

    def test_get_site_missing(self):
        self.assertIsNone(get_site(self.sites, "does_not_exist_xyz"))

    def test_regions_counts(self):
        counts = regions(self.sites)
        self.assertIsInstance(counts, dict)
        self.assertEqual(sum(counts.values()), len(self.sites))
        self.assertIn("kr", counts)
        self.assertGreaterEqual(counts["kr"], 1)

    def test_automation_levels_counts(self):
        counts = automation_levels(self.sites)
        self.assertIsInstance(counts, dict)
        self.assertEqual(sum(counts.values()), len(self.sites))
        self.assertIn("assisted_browser", counts)


class ValidateTests(unittest.TestCase):
    def test_shipped_registry_validates(self):
        result = validate_registry(load_registry())
        self.assertTrue(result["ok"], msg=f"errors: {result['errors']}")
        self.assertEqual(result["errors"], [])

    def test_detects_bad_gate(self):
        bad = [
            PlatformSite(
                platform_id="bad",
                region="global",
                platform_name="Bad",
                entry_type="self_publish",
                primary_url="https://example.com/",
                human_gates=["not_a_real_gate"],
                automation_level="api",
            )
        ]
        result = validate_registry(bad)
        self.assertFalse(result["ok"])
        self.assertTrue(any("not_a_real_gate" in e for e in result["errors"]))

    def test_detects_bad_automation_level(self):
        bad = [
            PlatformSite(
                platform_id="bad",
                region="global",
                platform_name="Bad",
                entry_type="self_publish",
                primary_url="https://example.com/",
                human_gates=[],
                automation_level="totally_invalid",
            )
        ]
        result = validate_registry(bad)
        self.assertFalse(result["ok"])

    def test_detects_bad_url(self):
        bad = [
            PlatformSite(
                platform_id="bad",
                region="global",
                platform_name="Bad",
                entry_type="self_publish",
                primary_url="ftp://example.com/",
                human_gates=[],
                automation_level="api",
            )
        ]
        result = validate_registry(bad)
        self.assertFalse(result["ok"])

    def test_all_gates_are_known(self):
        # 모든 적재된 게이트가 HUMAN_GATES 에 속하는지 직접 확인(이중 안전).
        for site in load_registry():
            for gate in site.human_gates:
                self.assertIn(gate, HUMAN_GATES)


if __name__ == "__main__":
    unittest.main()
