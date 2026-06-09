"""신규 오케스트레이션(잡/재생성/RAG/다운로드) 서비스 테스트."""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import service  # noqa: E402


class TestOrchestration(unittest.TestCase):
    def setUp(self):
        service.reset_store()

    def test_compose_project_stores_chapters_and_files(self):
        p = service.create_project("제로존 입문", topic="제로존 수학", n_chapters=5)
        r = service.compose_project(p["project_id"])
        self.assertTrue(r["ok"])
        proj = service.get_project(p["project_id"])
        self.assertEqual(proj["status"], "ready")
        self.assertEqual(len(proj["chapters"]), 5)
        self.assertIn("epub", proj["files"])
        self.assertTrue(Path(proj["files"]["epub"]).exists())

    def test_async_job_completes(self):
        p = service.create_project("비동기 책", topic="자동화", n_chapters=4)
        start = service.start_compose_job(p["project_id"])
        job_id = start["job_id"]
        # 잡 완료 대기(데몬 스레드)
        for _ in range(50):
            job = service.get_job(job_id)
            if job["state"] in ("done", "failed"):
                break
            time.sleep(0.1)
        job = service.get_job(job_id)
        self.assertEqual(job["state"], "done", job.get("error"))
        self.assertEqual(job["progress"], 1.0)
        # 단계 이벤트 존재
        stages = [e["stage"] for e in job["events"]]
        self.assertIn("outline", stages)
        self.assertIn("export", stages)
        # 결과가 프로젝트에 저장됨
        self.assertEqual(service.get_project(p["project_id"])["status"], "ready")

    def test_regenerate_chapter(self):
        p = service.create_project("재생성 책", topic="테스트 주제", n_chapters=4)
        service.compose_project(p["project_id"])
        before = service.get_project(p["project_id"])["chapters"][2]["content_md"]
        out = service.regenerate_chapter(p["project_id"], idx=2)
        self.assertTrue(out["ok"])
        self.assertEqual(out["idx"], 2)
        self.assertTrue(out["content_md"])
        self.assertTrue(out["coverage"]["ok"])

    def test_regenerate_unknown_chapter(self):
        p = service.create_project("책", topic="주제")
        service.compose_project(p["project_id"])
        with self.assertRaises(ValueError):
            service.regenerate_chapter(p["project_id"], idx=999)

    def test_rag_source_injection(self):
        p = service.create_project("RAG 책", topic="근거 기반 집필", n_chapters=4)
        service.add_source(p["project_id"], "s1", "제로존은 0=0 이라는 명제에서 출발한다.")
        r = service.compose_project(p["project_id"])
        self.assertTrue(r["ok"])
        self.assertEqual(len(service.get_project(p["project_id"])["sources"]), 1)

    def test_download_path(self):
        p = service.create_project("다운로드", topic="주제", n_chapters=3)
        service.compose_project(p["project_id"])
        epub = service.get_download_path(p["project_id"], "epub")
        self.assertTrue(epub and Path(epub).exists())
        self.assertIsNone(service.get_download_path("nope", "epub"))


if __name__ == "__main__":
    unittest.main()
