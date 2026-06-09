"""jobs.py — 잡 상태머신/이벤트 로그 테스트(stdlib unittest)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # apps/studio_api
import jobs  # noqa: E402


class TestJobStoreBasics(unittest.TestCase):
    def setUp(self):
        self.store = jobs.JobStore()
        self.store.reset()

    def test_create_defaults(self):
        job = self.store.create("proj_1")
        self.assertTrue(job["id"].startswith("job_"))
        self.assertEqual(len(job["id"]), len("job_") + 12)
        self.assertEqual(job["project_id"], "proj_1")
        self.assertEqual(job["type"], "compose")
        self.assertEqual(job["state"], jobs.STATE_QUEUED)
        self.assertEqual(job["progress"], 0.0)
        self.assertEqual(job["events"], [])
        self.assertEqual(job["checkpoint"], {})
        self.assertIsNone(job["error"])
        self.assertIsNone(job["result"])
        self.assertIn("created_at", job)
        self.assertIn("updated_at", job)

    def test_create_custom_type(self):
        job = self.store.create("proj_1", type="export")
        self.assertEqual(job["type"], "export")

    def test_get_and_missing(self):
        job = self.store.create("p")
        self.assertIs(self.store.get(job["id"]), job)
        self.assertIsNone(self.store.get("job_nope"))

    def test_list(self):
        self.store.create("p")
        self.store.create("p")
        self.assertEqual(len(self.store.list()), 2)

    def test_append_event(self):
        job = self.store.create("p")
        ev = self.store.append_event(job["id"], "write", "info", "stage_started",
                                     payload={"chapter": 3})
        self.assertEqual(ev["stage"], "write")
        self.assertEqual(ev["level"], "info")
        self.assertEqual(ev["message"], "stage_started")
        self.assertEqual(ev["payload"], {"chapter": 3})
        self.assertIn("ts", ev)
        self.assertEqual(len(self.store.get(job["id"])["events"]), 1)

    def test_append_event_default_payload(self):
        job = self.store.create("p")
        ev = self.store.append_event(job["id"], "write", "info", "x")
        self.assertEqual(ev["payload"], {})

    def test_set_updates_fields(self):
        job = self.store.create("p")
        self.store.set(job["id"], state="running", progress=0.5,
                       checkpoint={"index": 0})
        got = self.store.get(job["id"])
        self.assertEqual(got["state"], "running")
        self.assertEqual(got["progress"], 0.5)
        self.assertEqual(got["checkpoint"], {"index": 0})

    def test_set_missing_raises(self):
        with self.assertRaises(KeyError):
            self.store.set("job_nope", state="running")


class TestExecuteStages(unittest.TestCase):
    def setUp(self):
        self.store = jobs.JobStore()
        self.store.reset()

    def test_happy_path(self):
        job = self.store.create("p")

        def s1(ctx):
            return {"a": 1}

        def s2(ctx):
            return {"b": ctx["a"] + 1}

        def s3(ctx):
            return {"result": {"sum": ctx["a"] + ctx["b"]}}

        stages = [("outline", s1), ("write", s2), ("export", s3)]
        out = jobs.execute_stages(self.store, job["id"], stages)

        self.assertEqual(out["state"], jobs.STATE_DONE)
        self.assertEqual(out["progress"], 1.0)
        self.assertIsNone(out["error"])
        self.assertEqual(out["result"], {"sum": 3})

        msgs = [(e["stage"], e["message"]) for e in out["events"]]
        for name in ("outline", "write", "export"):
            self.assertIn((name, "stage_started"), msgs)
            self.assertIn((name, "stage_done"), msgs)
        self.assertIn((None, "job_done"), msgs)

        # stage_done payload 가 반환 dict 를 담는다
        done = [e for e in out["events"]
                if e["message"] == "stage_done" and e["stage"] == "outline"][0]
        self.assertEqual(done["payload"], {"a": 1})

    def test_checkpoint_progress_monotonic(self):
        job = self.store.create("p")
        stages = [("s%d" % i, lambda ctx: None) for i in range(4)]
        out = jobs.execute_stages(self.store, job["id"], stages)
        self.assertEqual(out["checkpoint"], {"completed_stage": "s3", "index": 3})
        self.assertEqual(out["progress"], 1.0)

    def test_failure_stops_pipeline(self):
        job = self.store.create("p")
        calls = []

        def ok(ctx):
            calls.append("ok")
            return {"x": 1}

        def boom(ctx):
            calls.append("boom")
            raise RuntimeError("kaboom")

        def never(ctx):
            calls.append("never")

        stages = [("outline", ok), ("write", boom), ("export", never)]
        out = jobs.execute_stages(self.store, job["id"], stages)

        self.assertEqual(out["state"], jobs.STATE_FAILED)
        self.assertLess(out["progress"], 1.0)
        self.assertEqual(calls, ["ok", "boom"])  # never not run
        self.assertIsNotNone(out["error"])
        self.assertEqual(out["error"]["stage"], "write")
        self.assertIn("kaboom", out["error"]["message"])
        self.assertFalse(out["error"]["retryable"])

        err_events = [e for e in out["events"] if e["message"] == "error"]
        self.assertEqual(len(err_events), 1)
        self.assertEqual(err_events[0]["level"], "error")

    def test_context_defaults_empty(self):
        job = self.store.create("p")
        out = jobs.execute_stages(self.store, job["id"], [("s", lambda c: None)])
        self.assertEqual(out["state"], jobs.STATE_DONE)
        self.assertIsNone(out["result"])


class TestRunInThread(unittest.TestCase):
    def setUp(self):
        self.store = jobs.JobStore()
        self.store.reset()

    def test_thread_completes(self):
        job = self.store.create("p")
        stages = [("a", lambda c: {"result": "ok"})]
        t = jobs.run_in_thread(self.store, job["id"], stages)
        t.join(timeout=5)
        self.assertFalse(t.is_alive())
        got = self.store.get(job["id"])
        self.assertEqual(got["state"], jobs.STATE_DONE)
        self.assertEqual(got["result"], "ok")


class TestSseFormat(unittest.TestCase):
    def test_known_event_name(self):
        ev = {"ts": "t", "stage": "write", "level": "info",
              "message": "stage_started", "payload": {"chapter": 3}}
        s = jobs.sse_format(ev)
        self.assertIsInstance(s, str)
        self.assertTrue(s.startswith("event: stage_started\n"))
        self.assertIn("data:", s)
        self.assertTrue(s.endswith("\n\n"))
        data_line = [ln for ln in s.splitlines() if ln.startswith("data:")][0]
        parsed = json.loads(data_line[len("data: "):])
        self.assertEqual(parsed["stage"], "write")
        self.assertEqual(parsed["chapter"], 3)

    def test_unknown_message_falls_back(self):
        ev = {"ts": "t", "stage": None, "level": "info",
              "message": "token_progress", "payload": {}}
        s = jobs.sse_format(ev)
        self.assertTrue(s.startswith("event: message\n"))
        data_line = [ln for ln in s.splitlines() if ln.startswith("data:")][0]
        json.loads(data_line[len("data: "):])  # valid JSON


if __name__ == "__main__":
    unittest.main()
