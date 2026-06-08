"""studio_api 서비스 계층 테스트(프레임워크 비의존, 실제 엔진 배선 검증)."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # apps/studio_api
import service  # noqa: E402

SAMPLE = "# 1장\n\n제로존은 2026년에 정리되었다.  공백  많음.\nISBN 978-89-12345-67-8 보존.\n"


class TestStudioService(unittest.TestCase):
    def setUp(self):
        service.reset_store()

    def test_health(self):
        h = service.health()
        self.assertTrue(h["ok"])
        self.assertIn("ebook_polisher", h["engine"])

    def test_create_and_get_project(self):
        p = service.create_project("제로존 정리집", topic="수학", genre="과학")
        self.assertTrue(p["project_id"].startswith("proj_"))
        self.assertEqual(service.get_project(p["project_id"])["title"], "제로존 정리집")
        self.assertEqual(len(service.list_projects()), 1)

    def test_create_project_requires_title(self):
        with self.assertRaises(ValueError):
            service.create_project("   ")

    def test_polish_text_wires_engine(self):
        r = service.polish_text(SAMPLE, title="t")
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["coverage"]["ok"])
        self.assertIn("2026", r["polished_markdown"])
        self.assertIn("978-89-12345-67-8", r["polished_markdown"])  # 무손실
        # 공백 축약 확인
        for line in r["polished_markdown"].splitlines():
            if line.strip() and not line.startswith("#"):
                self.assertNotIn("  ", line)

    def test_compose_start_runs_pipeline(self):
        p = service.create_project("책")
        out = service.compose_start(p["project_id"], manuscript=SAMPLE)
        self.assertEqual(out["status"], "polished")
        self.assertTrue(out["ok"])
        self.assertTrue(out["coverage_ok"])
        self.assertEqual(service.get_project(p["project_id"])["status"], "polished")

    def test_compose_start_without_manuscript(self):
        p = service.create_project("책")
        out = service.compose_start(p["project_id"])
        self.assertEqual(out["status"], "started")

    def test_compose_unknown_project(self):
        with self.assertRaises(KeyError):
            service.compose_start("proj_nope", manuscript=SAMPLE)


if __name__ == "__main__":
    unittest.main()
