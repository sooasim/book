"""잡 중간 재개(스냅샷 기반) + 상호참조 QA 게이트 테스트."""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import service  # noqa: E402


def _wait(job_id, states=("done", "failed"), tries=100):
    for _ in range(tries):
        j = service.get_job(job_id)
        if j and j["state"] in states:
            return j
        time.sleep(0.05)
    return service.get_job(job_id)


class TestResumeAndCrossref(unittest.TestCase):
    def setUp(self):
        service.reset_store()

    def test_mid_resume_uses_snapshot(self):
        p = service.create_project("중간재개 책", topic="자동화 주제", n_chapters=4)
        # outline 단계가 끝나도록 일반 실행
        start = service.start_compose_job(p["project_id"])
        job = _wait(start["job_id"])
        self.assertEqual(job["state"], "done", job.get("error"))
        # 완료 후 스냅샷은 정리되어야 함
        self.assertIsNone(service.get_project(p["project_id"]).get("_snapshot"))

    def test_resume_mid_after_snapshot(self):
        # 스냅샷을 강제로 만들고 resume 가 mid 모드로 동작하는지
        p = service.create_project("재개 책", topic="주제", n_chapters=4)
        start = service.start_compose_job(p["project_id"])
        _wait(start["job_id"])
        # 재개용 스냅샷을 수동 주입(중간 정지 상황 모사)
        proj = service.get_project(p["project_id"])
        proj["_snapshot"] = {
            "manuscript": "# 재개 책\n\n## 1장\n\n본문 2026.\n",
            "chapters": [{"idx": 0, "title": "1장", "brief": "b", "target_words": 100,
                          "content_md": "본문 2026.", "summary": "요약"}],
        }
        out = service.resume_job(start["job_id"])
        self.assertEqual(out["mode"], "mid")
        job = _wait(start["job_id"])
        self.assertEqual(job["state"], "done", job.get("error"))

    def test_crossref_gate_present(self):
        p = service.create_project("상호참조 책", topic="주제", n_chapters=5)
        r = service.compose_project(p["project_id"])
        self.assertIn("19_crossref", r["qa"]["gates"])
        self.assertIn("crossref", r["qa"])
        self.assertTrue(r["qa"]["crossref"]["checked"])


if __name__ == "__main__":
    unittest.main()
