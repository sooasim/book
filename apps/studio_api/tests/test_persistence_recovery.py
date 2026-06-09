"""잡 이벤트 영속화 + 재시작 복구, PDF 폴백, 표지 PNG, JWT 통합 테스트."""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _wait(service, job_id, tries=80):
    for _ in range(tries):
        j = service.get_job(job_id)
        if j and j["state"] in ("done", "failed"):
            return j
        time.sleep(0.05)
    return service.get_job(job_id)


class TestPersistenceRecovery(unittest.TestCase):
    def test_job_events_persisted_and_recovered(self):
        """파일 DB로 service 를 두 번 로드 → 잡과 이벤트가 복구된다."""
        db = str(Path(tempfile.mkdtemp()) / "oces.db")
        os.environ["OCES_DB"] = db
        try:
            import service as svc
            importlib.reload(svc)
            svc.reset_store()
            p = svc.create_project("복구 책", topic="주제", n_chapters=3)
            start = svc.start_compose_job(p["project_id"])
            job_id = start["job_id"]
            job = _wait(svc, job_id)
            self.assertEqual(job["state"], "done", job.get("error"))
            self.assertTrue(len(job["events"]) > 0)

            # "재시작" 시뮬레이션: 같은 DB로 service 재로딩
            importlib.reload(svc)
            recovered = svc.get_job(job_id)
            self.assertIsNotNone(recovered, "재시작 후 잡이 복구되어야 함")
            self.assertEqual(recovered["state"], "done")
            self.assertTrue(len(recovered["events"]) > 0)
            self.assertIsNotNone(svc.get_project(p["project_id"]))
        finally:
            os.environ.pop("OCES_DB", None)
            import service as svc2
            importlib.reload(svc2)  # 다른 테스트를 위해 인메모리로 복귀

    def test_pdf_and_cover_png_artifacts(self):
        import service as svc
        importlib.reload(svc)
        svc.reset_store()
        p = svc.create_project("PDF 표지 책", topic="주제", n_chapters=3)
        svc.compose_project(p["project_id"])
        pdf = svc.get_download_path(p["project_id"], "pdf")
        self.assertTrue(pdf and Path(pdf).exists())
        with open(pdf, "rb") as f:
            self.assertEqual(f.read(5), b"%PDF-")
        png = svc.get_download_path(p["project_id"], "cover_png")
        self.assertTrue(png and Path(png).exists())
        with open(png, "rb") as f:
            self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")
        # EPUB 여전히 유효
        with zipfile.ZipFile(svc.get_download_path(p["project_id"], "epub")) as zf:
            self.assertIsNone(zf.testzip())


if __name__ == "__main__":
    unittest.main()
