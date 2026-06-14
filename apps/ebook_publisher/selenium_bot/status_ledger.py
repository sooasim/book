"""게시 결과 원장 — 판매 URL/심사 상태를 CSV 에 누적 기록.

각 (book_id, platform_id) 한 행. 동일 조합 재기록 시 갱신(upsert).
표준 라이브러리(csv)만 사용.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ["book_id", "platform_id", "method", "status", "platform_url",
          "admin_url", "note", "updated_at"]

# 권장 상태값(자유 문자열 허용): prepared|submitted|in_review|live|rejected|paused|failed
DEFAULT_PATH = Path(__file__).resolve().parents[1] / "publish_results.csv"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(path: str | Path = DEFAULT_PATH) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def record(book_id: str, platform_id: str, status: str, *, method: str = "assist",
           platform_url: str = "", admin_url: str = "", note: str = "",
           path: str | Path = DEFAULT_PATH) -> dict:
    """게시 결과 한 건을 upsert 하고 그 행을 반환."""
    rows = load(path)
    row = {"book_id": book_id, "platform_id": platform_id, "method": method,
           "status": status, "platform_url": platform_url, "admin_url": admin_url,
           "note": note, "updated_at": _now()}
    replaced = False
    for i, r in enumerate(rows):
        if r.get("book_id") == book_id and r.get("platform_id") == platform_id:
            rows[i] = row
            replaced = True
            break
    if not replaced:
        rows.append(row)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    return row


def summary(path: str | Path = DEFAULT_PATH) -> dict:
    rows = load(path)
    by_status: dict[str, int] = {}
    by_platform: dict[str, int] = {}
    for r in rows:
        by_status[r.get("status", "")] = by_status.get(r.get("status", ""), 0) + 1
        by_platform[r.get("platform_id", "")] = by_platform.get(r.get("platform_id", ""), 0) + 1
    return {"total": len(rows), "by_status": by_status, "by_platform": by_platform}
