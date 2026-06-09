"""usage.py — 사용량/비용 추적 + 유저 스코핑 테스트(stdlib unittest)."""
from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # apps/studio_api
import usage  # noqa: E402


class TestEstimateTokens(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(usage.estimate_tokens(""), 0)
        self.assertEqual(usage.estimate_tokens("ab"), 1)
        self.assertEqual(usage.estimate_tokens("abcd"), 2)
        # 홀수 길이는 내림.
        self.assertEqual(usage.estimate_tokens("abc"), 1)
        self.assertEqual(usage.estimate_tokens("hello world"), len("hello world") // 2)


class TestRecordAndGet(unittest.TestCase):
    def setUp(self):
        self.t = usage.UsageTracker()

    def test_record_accumulates(self):
        self.t.record("alice", tokens=10, books=1)
        out = self.t.record("alice", tokens=5, books=2)
        self.assertEqual(out["tokens"], 15)
        self.assertEqual(out["books"], 3)
        self.assertEqual(out["quota"], usage.DEFAULT_TOKEN_QUOTA)

        got = self.t.get("alice")
        self.assertEqual(got["tokens"], 15)
        self.assertEqual(got["books"], 3)

    def test_record_returns_copy(self):
        out = self.t.record("alice", tokens=10)
        out["tokens"] = 999
        self.assertEqual(self.t.get("alice")["tokens"], 10)

    def test_unknown_user_get_returns_defaults(self):
        got = self.t.get("nobody")
        self.assertEqual(got, {"tokens": 0, "books": 0,
                               "quota": usage.DEFAULT_TOKEN_QUOTA})
        # get 은 유저를 생성하지 않는다.
        self.assertEqual(self.t.summary()["users"], 0)

    def test_default_user_constant(self):
        self.assertEqual(usage.DEFAULT_USER, "public")


class TestQuota(unittest.TestCase):
    def setUp(self):
        self.t = usage.UsageTracker()

    def test_set_quota_and_over_quota(self):
        self.t.record("bob", tokens=100)
        self.t.set_quota("bob", 50)
        self.assertTrue(self.t.over_quota("bob"))
        self.assertEqual(self.t.remaining("bob"), 50 - 100)  # 음수 허용

    def test_under_quota(self):
        self.t.set_quota("carol", 1000)
        self.t.record("carol", tokens=400)
        self.assertFalse(self.t.over_quota("carol"))
        self.assertEqual(self.t.remaining("carol"), 600)

    def test_over_quota_boundary_equal(self):
        self.t.set_quota("dan", 100)
        self.t.record("dan", tokens=100)
        # tokens >= quota -> over.
        self.assertTrue(self.t.over_quota("dan"))
        self.assertEqual(self.t.remaining("dan"), 0)

    def test_set_quota_creates_user(self):
        self.t.set_quota("eve", 5)
        got = self.t.get("eve")
        self.assertEqual(got["quota"], 5)
        self.assertEqual(got["tokens"], 0)

    def test_unknown_user_quota_defaults(self):
        self.assertFalse(self.t.over_quota("ghost"))
        self.assertEqual(self.t.remaining("ghost"), usage.DEFAULT_TOKEN_QUOTA)


class TestAggregation(unittest.TestCase):
    def setUp(self):
        self.t = usage.UsageTracker()

    def test_all_and_summary(self):
        self.t.record("alice", tokens=100, books=1)
        self.t.record("bob", tokens=200, books=3)
        self.t.record("alice", tokens=50, books=1)

        allu = self.t.all()
        self.assertEqual(set(allu), {"alice", "bob"})
        self.assertEqual(allu["alice"]["tokens"], 150)
        self.assertEqual(allu["alice"]["books"], 2)
        self.assertEqual(allu["bob"]["tokens"], 200)

        s = self.t.summary()
        self.assertEqual(s["users"], 2)
        self.assertEqual(s["total_tokens"], 350)
        self.assertEqual(s["total_books"], 5)  # alice 2 + bob 3

    def test_all_returns_copies(self):
        self.t.record("alice", tokens=10)
        allu = self.t.all()
        allu["alice"]["tokens"] = 999
        self.assertEqual(self.t.get("alice")["tokens"], 10)

    def test_empty_summary(self):
        self.assertEqual(self.t.summary(),
                         {"users": 0, "total_tokens": 0, "total_books": 0})


class TestReset(unittest.TestCase):
    def test_reset_clears(self):
        t = usage.UsageTracker()
        t.record("alice", tokens=100, books=2)
        t.set_quota("bob", 5)
        t.reset()
        self.assertEqual(t.all(), {})
        self.assertEqual(t.summary(),
                         {"users": 0, "total_tokens": 0, "total_books": 0})


class TestSingleton(unittest.TestCase):
    def test_module_singleton_exists(self):
        self.assertIsInstance(usage.tracker, usage.UsageTracker)


class TestThreadSafety(unittest.TestCase):
    def test_concurrent_record_sums_correctly(self):
        t = usage.UsageTracker()
        n_threads = 10
        per_thread = 100

        def worker():
            for _ in range(per_thread):
                t.record("shared", tokens=1, books=1)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        got = t.get("shared")
        self.assertEqual(got["tokens"], n_threads * per_thread)
        self.assertEqual(got["books"], n_threads * per_thread)
        self.assertEqual(t.summary()["users"], 1)


if __name__ == "__main__":
    unittest.main()
