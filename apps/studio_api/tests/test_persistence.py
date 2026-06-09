"""persistence.py — SQLite 영속화 계층 테스트 (stdlib unittest)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # apps/studio_api
import persistence  # noqa: E402


def _sample_project(project_id="proj_1", title="Sample"):
    return {
        "project_id": project_id,
        "title": title,
        "status": "draft",
        "chapters": [
            {"idx": 0, "title": "Intro", "content_md": "# Intro\nhi"},
            {"idx": 1, "title": "Body", "content_md": "## Body\nmore"},
        ],
        "meta": {"n_chapters": 2, "language": "한국어"},
    }


def _sample_job(job_id="job_1", project_id="proj_1"):
    return {
        "id": job_id,
        "project_id": project_id,
        "type": "compose",
        "state": "queued",
        "progress": 0.0,
        "events": [{"at": "t0", "kind": "created"}],
        "checkpoint": {},
        "error": None,
        "result": None,
    }


class TestProjectRoundTrip(unittest.TestCase):
    def setUp(self):
        self.store = persistence.Store()  # :memory:

    def tearDown(self):
        self.store.close()

    def test_save_then_load(self):
        proj = _sample_project()
        self.store.save_project(proj)
        loaded = self.store.load_projects()
        self.assertEqual(len(loaded), 1)
        self.assertIn("proj_1", loaded)
        self.assertEqual(loaded["proj_1"], proj)
        # nested fields preserved
        self.assertEqual(loaded["proj_1"]["chapters"][1]["title"], "Body")
        self.assertEqual(loaded["proj_1"]["meta"]["language"], "한국어")

    def test_upsert_updates_in_place(self):
        self.store.save_project(_sample_project(title="First"))
        self.store.save_project(_sample_project(title="Second"))
        loaded = self.store.load_projects()
        self.assertEqual(len(loaded), 1)  # still one row
        self.assertEqual(loaded["proj_1"]["title"], "Second")

    def test_skip_when_no_project_id(self):
        self.store.save_project({"title": "no id here"})
        self.assertEqual(self.store.load_projects(), {})

    def test_non_serializable_value_saves(self):
        proj = _sample_project()
        proj["tags"] = {"a", "b"}  # a set is not JSON-serializable
        # must not raise
        self.store.save_project(proj)
        loaded = self.store.load_projects()
        self.assertIn("proj_1", loaded)
        # default=str stringifies the set rather than crashing
        self.assertIsInstance(loaded["proj_1"]["tags"], str)


class TestJobRoundTrip(unittest.TestCase):
    def setUp(self):
        self.store = persistence.Store()

    def tearDown(self):
        self.store.close()

    def test_save_then_load(self):
        job = _sample_job()
        self.store.save_job(job)
        loaded = self.store.load_jobs()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded["job_1"], job)
        self.assertEqual(loaded["job_1"]["events"][0]["kind"], "created")

    def test_upsert_updates_in_place(self):
        job = _sample_job()
        self.store.save_job(job)
        job2 = _sample_job()
        job2["state"] = "running"
        job2["progress"] = 0.5
        self.store.save_job(job2)
        loaded = self.store.load_jobs()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded["job_1"]["state"], "running")
        self.assertEqual(loaded["job_1"]["progress"], 0.5)

    def test_skip_when_no_id(self):
        self.store.save_job({"project_id": "proj_1"})
        self.assertEqual(self.store.load_jobs(), {})


class TestDeleteAll(unittest.TestCase):
    def test_clears_both_tables(self):
        store = persistence.Store()
        store.save_project(_sample_project())
        store.save_job(_sample_job())
        self.assertEqual(len(store.load_projects()), 1)
        self.assertEqual(len(store.load_jobs()), 1)
        store.delete_all()
        self.assertEqual(store.load_projects(), {})
        self.assertEqual(store.load_jobs(), {})
        store.close()


class TestPersistenceAcrossInstances(unittest.TestCase):
    """tempfile을 사용해 실제 디스크 영속화를 검증한다."""

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.path)  # let sqlite create it fresh

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            p = self.path + suffix
            if os.path.exists(p):
                os.unlink(p)

    def test_data_survives_new_store(self):
        proj = _sample_project()
        job = _sample_job()
        s1 = persistence.Store(db_path=self.path)
        s1.save_project(proj)
        s1.save_job(job)
        s1.close()

        s2 = persistence.Store(db_path=self.path)
        projects = s2.load_projects()
        jobs = s2.load_jobs()
        s2.close()

        self.assertEqual(projects.get("proj_1"), proj)
        self.assertEqual(jobs.get("job_1"), job)


if __name__ == "__main__":
    unittest.main()
