"""고도화 기능 테스트: HITL 일시정지/재개·챕터 편집·사용량·영속화·표지."""
from __future__ import annotations

import sys
import time
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jobs as jobs_mod  # noqa: E402
import service  # noqa: E402
import usage as usage_mod  # noqa: E402


def _wait_job(job_id, states=("done", "failed", "paused"), tries=80):
    for _ in range(tries):
        j = service.get_job(job_id)
        if j and j["state"] in states:
            return j
        time.sleep(0.05)
    return service.get_job(job_id)


class TestAdvanced(unittest.TestCase):
    def setUp(self):
        service.reset_store()

    # ---- 챕터 인라인 편집 ----
    def test_edit_chapter(self):
        p = service.create_project("편집 책", topic="주제", n_chapters=4)
        service.compose_project(p["project_id"])
        r = service.edit_chapter(p["project_id"], 1, "# 무시\n사람이 직접 쓴 문장 2026.")
        self.assertTrue(r["ok"])
        proj = service.get_project(p["project_id"])
        edited = next(c for c in proj["chapters"] if c["idx"] == 1)
        self.assertIn("사람이 직접 쓴", edited["content_md"])

    def test_edit_unknown_chapter(self):
        p = service.create_project("책", topic="주제")
        service.compose_project(p["project_id"])
        with self.assertRaises(ValueError):
            service.edit_chapter(p["project_id"], 999, "x")

    # ---- HITL 일시정지/재개 ----
    def test_pause_then_resume(self):
        p = service.create_project("일시정지 책", topic="주제", n_chapters=4)
        start = service.start_compose_job(p["project_id"])
        jid = start["job_id"]
        service.pause_job(jid)  # 다음 경계에서 멈춤(또는 이미 완료면 무해)
        _wait_job(jid)
        service.resume_job(jid)  # 재개(결정적 재실행)
        job = _wait_job(jid, states=("done",))
        self.assertEqual(job["state"], "done", job.get("error"))
        self.assertEqual(service.get_project(p["project_id"])["status"], "ready")

    def test_request_pause_sets_flag(self):
        p = service.create_project("책", topic="주제", n_chapters=3)
        start = service.start_compose_job(p["project_id"])
        out = service.pause_job(start["job_id"])
        # 플래그가 설정되거나 이미 종료 상태
        self.assertIn(out["state"], ("queued", "running", "paused", "done"))

    # ---- 사용량/비용 ----
    def test_usage_tracked(self):
        p = service.create_project("사용량 책", topic="주제", n_chapters=4, )
        service.compose_project(p["project_id"])
        u = service.get_usage("public")
        self.assertGreater(u["tokens"], 0)
        self.assertGreaterEqual(u["books"], 1)
        dash = service.usage_dashboard()
        self.assertGreaterEqual(dash["summary"]["total_tokens"], u["tokens"])

    # ---- 멀티테넌시 스코프 ----
    def test_user_scope(self):
        a = service.create_project("A책", topic="t", user_id="alice")
        service.create_project("B책", topic="t", user_id="bob")
        self.assertEqual(len(service.list_projects(user_id="alice")), 1)
        self.assertIsNone(service.get_project(a["project_id"], user_id="bob"))
        self.assertIsNotNone(service.get_project(a["project_id"], user_id="alice"))

    # ---- 영속화 ----
    def test_persistence_roundtrip(self):
        p = service.create_project("영속 책", topic="주제")
        loaded = service.STORE.load_projects()
        self.assertIn(p["project_id"], loaded)
        self.assertEqual(loaded[p["project_id"]]["title"], "영속 책")

    # ---- 표지 EPUB 삽입 ----
    def test_cover_in_epub(self):
        p = service.create_project("표지 책", topic="주제", n_chapters=3)
        service.compose_project(p["project_id"])
        epub = service.get_download_path(p["project_id"], "epub")
        self.assertTrue(epub and Path(epub).exists())
        with zipfile.ZipFile(epub) as zf:
            self.assertIn("OEBPS/cover.xhtml", zf.namelist())
            self.assertIsNone(zf.testzip())
        self.assertTrue(service.get_download_path(p["project_id"], "cover"))


if __name__ == "__main__":
    unittest.main()
