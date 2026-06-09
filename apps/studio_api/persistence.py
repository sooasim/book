"""persistence.py — SQLite 영속화 계층.

In-memory dict 형태로 관리되던 projects/jobs를 SQLite에 JSON 문서로 저장한다.
프로세스 재시작 후에도 데이터가 살아남으며, 동일한 JSON-document shape으로
향후 PostgreSQL 마이그레이션의 씨앗 역할을 한다.

stdlib만 사용한다 (sqlite3, json, threading). 결정적(deterministic)이다.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone

__all__ = ["Store"]


def _now_iso() -> str:
    """UTC ISO-8601 타임스탬프."""
    return datetime.now(timezone.utc).isoformat()


def _dumps(obj: dict) -> str:
    """비-직렬화 값(예: set)도 default=str로 견고하게 처리."""
    return json.dumps(obj, ensure_ascii=False, default=str)


class Store:
    """SQLite 기반 projects/jobs 영속 저장소."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._create_tables()

    def _create_tables(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    data       TEXT NOT NULL,
                    updated_at TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id     TEXT PRIMARY KEY,
                    data       TEXT NOT NULL,
                    updated_at TEXT
                )
                """
            )
            self._conn.commit()

    # ----- projects -----------------------------------------------------
    def save_project(self, project: dict) -> None:
        """project["project_id"] 기준 upsert. id가 없으면 조용히 무시."""
        project_id = project.get("project_id")
        if not project_id:
            return
        payload = _dumps(project)
        ts = _now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO projects (project_id, data, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    data = excluded.data,
                    updated_at = excluded.updated_at
                """,
                (project_id, payload, ts),
            )
            self._conn.commit()

    def load_projects(self) -> dict[str, dict]:
        """{project_id: dict} 형태로 모든 행 반환."""
        cur = self._conn.execute("SELECT project_id, data FROM projects")
        return {row[0]: json.loads(row[1]) for row in cur.fetchall()}

    # ----- jobs ---------------------------------------------------------
    def save_job(self, job: dict) -> None:
        """job["id"] 기준 upsert. id가 없으면 조용히 무시."""
        job_id = job.get("id")
        if not job_id:
            return
        payload = _dumps(job)
        ts = _now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO jobs (job_id, data, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    data = excluded.data,
                    updated_at = excluded.updated_at
                """,
                (job_id, payload, ts),
            )
            self._conn.commit()

    def load_jobs(self) -> dict[str, dict]:
        """{id: dict} 형태로 모든 행 반환."""
        cur = self._conn.execute("SELECT job_id, data FROM jobs")
        return {row[0]: json.loads(row[1]) for row in cur.fetchall()}

    # ----- maintenance --------------------------------------------------
    def delete_all(self) -> None:
        """두 테이블 모두 비운다 (테스트용)."""
        with self._lock:
            self._conn.execute("DELETE FROM projects")
            self._conn.execute("DELETE FROM jobs")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
