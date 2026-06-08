import unittest

from ebook_polisher.models import TaskNode
from ebook_polisher.scheduler import (
    CIDScheduler,
    has_cycle,
    ready_tasks,
    unresolved_dependencies,
)


class TestSchedulerHelpers(unittest.TestCase):
    def test_unresolved_dependencies(self):
        task = TaskNode(task_id="t2", role="polish", dependencies=["t1"])
        self.assertEqual(unresolved_dependencies(task, set()), ["t1"])
        self.assertEqual(unresolved_dependencies(task, {"t1"}), [])

    def test_ready_tasks(self):
        t1 = TaskNode(task_id="t1", role="r")
        t2 = TaskNode(task_id="t2", role="r", dependencies=["t1"])
        ready = ready_tasks([t1, t2], set())
        self.assertEqual([t.task_id for t in ready], ["t1"])


class TestCIDScheduler(unittest.TestCase):
    def test_dag_runs_to_verified_in_order(self):
        # 체인 t1<-t2<-t3 + 독립 t4
        t1 = TaskNode(task_id="t1", role="r")
        t2 = TaskNode(task_id="t2", role="r", dependencies=["t1"])
        t3 = TaskNode(task_id="t3", role="r", dependencies=["t2"])
        t4 = TaskNode(task_id="t4", role="r")

        order = []
        lock_free = []  # runner 는 단순 append

        def runner(task):
            order.append(task.task_id)

        scheduler = CIDScheduler(runner=runner)
        result = scheduler.run([t1, t2, t3, t4])

        for t in result:
            self.assertEqual(t.status, "verified")

        # 의존성 순서: t1 이 t2 보다, t2 가 t3 보다 먼저 실행됨
        self.assertLess(order.index("t1"), order.index("t2"))
        self.assertLess(order.index("t2"), order.index("t3"))
        # t4 는 실행됨
        self.assertIn("t4", order)
        self.assertEqual(len(order), 4)

    def test_default_runner_noop(self):
        t1 = TaskNode(task_id="t1", role="r")
        scheduler = CIDScheduler()
        result = scheduler.run([t1])
        self.assertEqual(result[0].status, "verified")

    def test_cycle_blocks(self):
        a = TaskNode(task_id="a", role="r", dependencies=["b"])
        b = TaskNode(task_id="b", role="r", dependencies=["a"])
        self.assertTrue(has_cycle([a, b]))

        scheduler = CIDScheduler()
        result = scheduler.run([a, b])
        for t in result:
            self.assertEqual(t.status, "blocked")

    def test_no_cycle(self):
        t1 = TaskNode(task_id="t1", role="r")
        t2 = TaskNode(task_id="t2", role="r", dependencies=["t1"])
        self.assertFalse(has_cycle([t1, t2]))


if __name__ == "__main__":
    unittest.main()
