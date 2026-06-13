"""collector.py 단위 테스트 — Selenium/네트워크 없음(가짜 드라이버 사용)."""
import json
import pathlib
import sys
import tempfile
import unittest

# 테스트 CWD == selenium_bot. 패키지 부모를 sys.path 에 추가.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from selenium_bot.models import PlatformSite  # noqa: E402
from selenium_bot.collector import (  # noqa: E402
    normalize_url,
    probe_plan,
    probe_sites,
    summarize_probe,
    write_report,
)


def _sample_sites():
    return [
        PlatformSite(
            platform_id="alpha",
            region="global",
            platform_name="Alpha",
            entry_type="self_publish",
            primary_url="https://alpha.example.com/",
            signup_url="https://alpha.example.com/signup",
        ),
        PlatformSite(
            platform_id="beta",
            region="kr",
            platform_name="Beta",
            entry_type="direct_store",
            primary_url="beta.example.com",
            signup_url="",
        ),
    ]


class FakeDriver:
    """Selenium WebDriver 흉내(덕 타이핑): .get(url) / .title / .page_source.

    매핑된 URL 에 대해 정해진 제목/본문을 돌려주고,
    미등록 URL 은 예외를 던져 reachable=False 경로를 검증한다.
    """

    def __init__(self, pages):
        # pages: {url: {"title": str, "page_source": str}}
        self._pages = pages
        self.title = ""
        self.page_source = ""
        self.visited = []

    def get(self, url):
        self.visited.append(url)
        if url not in self._pages:
            raise RuntimeError(f"cannot reach {url}")
        self.title = self._pages[url]["title"]
        self.page_source = self._pages[url]["page_source"]


class NormalizeUrlTests(unittest.TestCase):
    def test_adds_scheme_when_missing(self):
        self.assertEqual(normalize_url("example.com"), "https://example.com")

    def test_adds_scheme_with_path(self):
        self.assertEqual(
            normalize_url("example.com/books"), "https://example.com/books"
        )

    def test_strips_whitespace(self):
        self.assertEqual(
            normalize_url("  https://example.com/  "), "https://example.com/"
        )

    def test_keeps_existing_https(self):
        self.assertEqual(normalize_url("https://x.io/y"), "https://x.io/y")

    def test_keeps_http(self):
        self.assertEqual(normalize_url("http://x.io"), "http://x.io")

    def test_empty_stays_empty(self):
        self.assertEqual(normalize_url(""), "")
        self.assertEqual(normalize_url("   "), "")


class ProbePlanTests(unittest.TestCase):
    def test_length_matches(self):
        sites = _sample_sites()
        plan = probe_plan(sites)
        self.assertEqual(len(plan), len(sites))

    def test_fields_are_none_and_present(self):
        plan = probe_plan(_sample_sites())
        first = plan[0]
        self.assertEqual(first["platform_id"], "alpha")
        self.assertEqual(first["primary_url"], "https://alpha.example.com/")
        self.assertEqual(first["signup_url"], "https://alpha.example.com/signup")
        self.assertIsNone(first["reachable"])
        self.assertIsNone(first["title"])
        self.assertIsNone(first["has_signup_link"])

    def test_empty_sites(self):
        self.assertEqual(probe_plan([]), [])


class SummarizeTests(unittest.TestCase):
    def test_counts(self):
        results = [
            {"reachable": True},
            {"reachable": True},
            {"reachable": False},
            {"reachable": None},
        ]
        summary = summarize_probe(results)
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["reachable_true"], 2)
        self.assertEqual(summary["reachable_false"], 1)
        self.assertEqual(summary["reachable_none"], 1)

    def test_empty(self):
        summary = summarize_probe([])
        self.assertEqual(
            summary,
            {
                "total": 0,
                "reachable_true": 0,
                "reachable_false": 0,
                "reachable_none": 0,
            },
        )

    def test_plan_is_all_none(self):
        summary = summarize_probe(probe_plan(_sample_sites()))
        self.assertEqual(summary["reachable_none"], 2)
        self.assertEqual(summary["reachable_true"], 0)


class ProbeSitesTests(unittest.TestCase):
    def test_none_driver_raises(self):
        with self.assertRaises(RuntimeError):
            probe_sites(_sample_sites(), driver=None)

    def test_none_driver_default_arg_raises(self):
        with self.assertRaises(RuntimeError):
            probe_sites(_sample_sites())

    def test_fake_driver_fills_reachable_and_detects_signup(self):
        sites = _sample_sites()
        pages = {
            "https://alpha.example.com/": {
                "title": "Alpha Home",
                "page_source": "<html><body><a href='/signup'>Sign Up now</a></body></html>",
            },
            # beta.example.com 은 normalize 후 https 가 붙는다.
            "https://beta.example.com": {
                "title": "Beta",
                "page_source": "<html><body>no auth links here</body></html>",
            },
        }
        driver = FakeDriver(pages)
        results = probe_sites(sites, driver=driver)

        alpha = results[0]
        self.assertTrue(alpha["reachable"])
        self.assertEqual(alpha["title"], "Alpha Home")
        self.assertTrue(alpha["has_signup_link"])

        beta = results[1]
        self.assertTrue(beta["reachable"])
        self.assertEqual(beta["title"], "Beta")
        self.assertFalse(beta["has_signup_link"])

    def test_detects_korean_signup_token(self):
        sites = [
            PlatformSite(
                platform_id="kr1",
                region="kr",
                platform_name="KR",
                entry_type="direct_store",
                primary_url="https://kr.example.com/",
            )
        ]
        pages = {
            "https://kr.example.com/": {
                "title": "한국 사이트",
                "page_source": "<html><body><a>회원가입</a></body></html>",
            }
        }
        results = probe_sites(sites, driver=FakeDriver(pages))
        self.assertTrue(results[0]["has_signup_link"])

    def test_unreachable_sets_false(self):
        sites = [
            PlatformSite(
                platform_id="dead",
                region="global",
                platform_name="Dead",
                entry_type="direct_store",
                primary_url="https://dead.example.com/",
            )
        ]
        # 빈 매핑 -> get() 이 예외 -> reachable False
        results = probe_sites(sites, driver=FakeDriver({}))
        self.assertFalse(results[0]["reachable"])
        self.assertIsNone(results[0]["title"])
        self.assertIsNone(results[0]["has_signup_link"])


class WriteReportTests(unittest.TestCase):
    def test_writes_valid_json(self):
        results = probe_plan(_sample_sites())
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "report.json"
            returned = write_report(results, out)
            self.assertEqual(returned, str(out))
            self.assertTrue(out.exists())
            with open(out, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self.assertIn("summary", data)
            self.assertIn("results", data)
            self.assertEqual(len(data["results"]), 2)
            self.assertEqual(data["summary"]["total"], 2)


if __name__ == "__main__":
    unittest.main()
