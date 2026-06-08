"""CID 의존성 DAG 스케줄러 (웨이브 단위 병렬 실행).

작업 노드(TaskNode)는 의존성 DAG를 형성한다. 각 웨이브에서 준비된(ready)
모든 작업을 ThreadPoolExecutor 로 병렬 실행하고 "verified" 로 표시한 뒤,
완료 집합을 갱신해 다음 웨이브를 진행한다. 순환/차단으로 더 이상 준비되는
작업이 없으면 남은 pending 작업을 "blocked" 로 표시하고 종료한다.

완료 집합은 스레드 실행 순서와 무관하게 결정적(deterministic)이다.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from ebook_polisher.models import TaskNode


def unresolved_dependencies(task: TaskNode, completed: set[str]) -> list[str]:
    """완료되지 않은 의존성 task_id 목록."""
    return [dep for dep in task.dependencies if dep not in completed]


def ready_tasks(tasks: list[TaskNode], completed: set[str]) -> list[TaskNode]:
    """status=='pending' 이고 모든 의존성이 완료된 작업들."""
    return [
        task
        for task in tasks
        if task.status == "pending"
        and not unresolved_dependencies(task, completed)
    ]


def has_cycle(tasks: list[TaskNode]) -> bool:
    """의존성 그래프에 순환이 존재하면 True.

    tasks 내부에 정의된 task_id 사이의 간선만 고려한다(외부 의존성은 무시).
    """
    ids = {t.task_id for t in tasks}
    graph: dict[str, list[str]] = {
        t.task_id: [d for d in t.dependencies if d in ids] for t in tasks
    }
    # 0=미방문, 1=방문중, 2=완료
    state: dict[str, int] = {tid: 0 for tid in graph}

    def visit(node: str) -> bool:
        state[node] = 1
        for dep in graph.get(node, []):
            if state[dep] == 1:
                return True
            if state[dep] == 0 and visit(dep):
                return True
        state[node] = 2
        return False

    return any(state[tid] == 0 and visit(tid) for tid in graph)


class CIDScheduler:
    """웨이브 단위 병렬 스케줄러."""

    def __init__(self, runner: Optional[Callable[[TaskNode], None]] = None) -> None:
        self.runner: Callable[[TaskNode], None] = runner or (lambda task: None)

    def _execute_wave(self, wave: list[TaskNode]) -> None:
        """한 웨이브의 작업들을 병렬 실행한다."""
        if not wave:
            return
        with ThreadPoolExecutor(max_workers=len(wave)) as pool:
            futures = [pool.submit(self.runner, task) for task in wave]
            for fut in futures:
                fut.result()

    def run(self, tasks: list[TaskNode]) -> list[TaskNode]:
        completed: set[str] = set()

        while True:
            wave = ready_tasks(tasks, completed)
            if not wave:
                break
            self._execute_wave(wave)
            # 결정적 완료 집합: 실행 순서와 무관하게 웨이브 전체를 일괄 완료 처리.
            for task in wave:
                task.status = "verified"
                completed.add(task.task_id)

        # 남은 pending 작업은 순환/차단 상태이므로 blocked 로 표시.
        for task in tasks:
            if task.status == "pending":
                task.status = "blocked"

        return tasks
