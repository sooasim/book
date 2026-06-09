"""OneClick eBook Studio — 잡/상태머신 + 이벤트 로그 (순수 stdlib).

오케스트레이션의 *제너릭* 골격만 담는다. 실제 컴포즈 단계 로직(outline/write/
edit/...)은 다른 모듈에서 정의되어 `execute_stages`에 (name, fn) 콜러블 목록으로
주입된다.

설계 원칙:
- 결정적(deterministic): 외부 입력 외에는 시간/스레드 순서에 의존하지 않는다
  (타임스탬프 제외). 상태 전이는 명세된 순서대로만 일어난다.
- 스레드 안전(thread-safe): 모든 저장소 변경은 단일 Lock 으로 직렬화한다.

상태머신(02-architecture.md §5):
    queued -> running -> done | failed   (paused 는 HITL 용 예약)
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

# 잡 상태 상수
STATE_QUEUED = "queued"
STATE_RUNNING = "running"
STATE_PAUSED = "paused"  # HITL 체크포인트용 예약(현재 골격에서는 미사용 전이)
STATE_DONE = "done"
STATE_FAILED = "failed"

# 단계 콜러블 시그니처: fn(context: dict) -> dict | None
StageFn = Callable[[dict], Optional[dict]]
Stage = tuple[str, StageFn]


def _now_iso() -> str:
    """UTC ISO-8601 타임스탬프(초 단위까지, 'Z' 접미)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


class JobStore:
    """인메모리 잡 저장소. 모든 공개 메서드는 스레드 안전하다."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}
        self._persister = None  # Optional[callable(job_dict)] — 영속화 훅

    def set_persister(self, fn) -> None:
        """잡 변경 시 호출될 영속화 콜백 등록(예: SQLite 저장)."""
        self._persister = fn

    def load(self, jobs: dict) -> None:
        """외부 저장소에서 잡들을 복원(재시작 복구)."""
        with self._lock:
            for jid, job in jobs.items():
                self._jobs[jid] = job

    def _persist(self, job: Optional[dict]) -> None:
        if self._persister and job is not None:
            try:
                self._persister(dict(job))
            except Exception:  # noqa: BLE001 — 영속화 실패가 잡 실행을 막지 않음
                pass

    def reset(self) -> None:
        """테스트용: 모든 잡 제거."""
        with self._lock:
            self._jobs.clear()

    def create(self, project_id: str, type: str = "compose") -> dict:
        """새 잡 생성. state='queued', progress=0.0, 빈 이벤트 목록."""
        job_id = "job_" + uuid.uuid4().hex[:12]
        ts = _now_iso()
        job = {
            "id": job_id,
            "project_id": project_id,
            "type": type,
            "state": STATE_QUEUED,
            "current_stage": None,
            "progress": 0.0,
            "events": [],
            "checkpoint": {},
            "error": None,
            "created_at": ts,
            "updated_at": ts,
            "result": None,
        }
        with self._lock:
            self._jobs[job_id] = job
        self._persist(job)
        return job

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[dict]:
        with self._lock:
            return list(self._jobs.values())

    def append_event(
        self,
        job_id: str,
        stage: Optional[str],
        level: str,
        message: str,
        payload: Optional[dict] = None,
    ) -> dict:
        """이벤트 한 건을 events 에 추가하고 updated_at 갱신. 추가된 이벤트 반환."""
        event = {
            "ts": _now_iso(),
            "stage": stage,
            "level": level,
            "message": message,
            "payload": payload if payload is not None else {},
        }
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            job["events"].append(event)
            job["updated_at"] = event["ts"]
        self._persist(job)
        return event

    def set(self, job_id: str, **fields: Any) -> dict:
        """임의 필드 갱신(state/current_stage/progress/checkpoint/error/result 등).

        updated_at 을 새로 고친다. 변경된 잡 반환.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            for key, value in fields.items():
                job[key] = value
            job["updated_at"] = _now_iso()
        self._persist(job)
        return job


# 이벤트 message 값으로 쓰이는 잡/단계 라이프사이클 타입
EV_STAGE_STARTED = "stage_started"
EV_STAGE_DONE = "stage_done"
EV_JOB_DONE = "job_done"
EV_ERROR = "error"

# sse_format 에서 SSE event 이름으로 승격할 수 있는 message 집합
_SSE_EVENT_NAMES = {EV_STAGE_STARTED, EV_STAGE_DONE, EV_JOB_DONE, EV_ERROR}

# payload 를 stage_done 이벤트에 그대로 실어줄지 결정하는 임계치(키 개수).
_SMALL_PAYLOAD_KEYS = 8


STATE_PAUSED = "paused"


def request_pause(store: JobStore, job_id: str) -> dict:
    """HITL: 다음 단계 경계에서 멈추도록 일시정지를 요청한다."""
    return store.set(job_id, pause_requested=True)


def execute_stages(
    store: JobStore,
    job_id: str,
    stages: Iterable[Stage],
    context: Optional[dict] = None,
    start_index: int = 0,
) -> dict:
    """잡의 단계 목록을 순차 실행하는 동기 오케스트레이터.

    - state='running' 으로 전환.
    - 각 단계 i 에 대해:
        current_stage=name, 'stage_started'(info) 이벤트 추가
        fn(context) 호출 → dict 반환 시 context 에 머지
        progress=(i+1)/len(stages)
        'stage_done' 이벤트 추가(반환 dict 가 작으면 payload 로 포함, 아니면 {})
        checkpoint={"completed_stage": name, "index": i} 저장
    - 예외 발생 시: 'error'(error) 이벤트 추가, state='failed', error 기록 후
      잡을 반환(재발생하지 않음). 이후 단계는 실행하지 않는다.
    - 전 단계 성공 시: state='done', progress=1.0, result=context.get("result"),
      'job_done' 이벤트 추가. 잡을 반환.
    """
    stage_list = list(stages)
    total = len(stage_list)
    if context is None:
        context = {}

    # 잡이 외부에서 제거(reset/delete)되면 set 이 KeyError 를 던질 수 있다.
    # 데몬 스레드에서 조용히 종료하도록 전체를 방어한다.
    try:
        return _run_stages(store, job_id, stage_list, context, total, start_index)
    except KeyError:
        return store.get(job_id)


def _run_stages(store, job_id, stage_list, context, total, start_index):
    store.set(job_id, state=STATE_RUNNING, pause_requested=False)

    for i, (name, fn) in enumerate(stage_list):
        if i < start_index:
            continue  # 재개: 이미 완료된 단계는 건너뛴다
        if store.get(job_id) is None:
            return None  # 잡이 사라졌으면 중단
        # HITL: 단계 경계에서 일시정지 요청 확인
        job = store.get(job_id)
        if job and job.get("pause_requested"):
            store.set(job_id, state=STATE_PAUSED,
                      checkpoint={"completed_stage": stage_list[i - 1][0] if i else None,
                                  "index": i - 1}, pause_requested=False)
            store.append_event(job_id, name, "info", "paused", payload={"next_index": i})
            return store.get(job_id)
        store.set(job_id, current_stage=name)
        store.append_event(job_id, name, "info", EV_STAGE_STARTED)
        try:
            returned = fn(context)
        except Exception as exc:  # noqa: BLE001 — 의도적으로 모든 예외를 잡 실패로 변환
            error = {"retryable": False, "stage": name, "message": str(exc)}
            store.append_event(job_id, name, "error", EV_ERROR, payload=error)
            store.set(job_id, state=STATE_FAILED, error=error)
            return store.get(job_id)

        if isinstance(returned, dict):
            context.update(returned)

        progress = (i + 1) / total if total else 1.0
        store.set(job_id, progress=progress)

        if isinstance(returned, dict) and len(returned) <= _SMALL_PAYLOAD_KEYS:
            done_payload = dict(returned)
        else:
            done_payload = {}
        store.append_event(job_id, name, "info", EV_STAGE_DONE, payload=done_payload)

        store.set(job_id, checkpoint={"completed_stage": name, "index": i})

    store.set(
        job_id,
        state=STATE_DONE,
        progress=1.0,
        result=context.get("result"),
    )
    store.append_event(job_id, None, "info", EV_JOB_DONE, payload={"job_id": job_id})
    return store.get(job_id)


def run_in_thread(
    store: JobStore,
    job_id: str,
    stages: Iterable[Stage],
    context: Optional[dict] = None,
    start_index: int = 0,
) -> threading.Thread:
    """execute_stages 를 데몬 스레드에서 실행하고 그 스레드를 반환한다.

    호출자는 thread.join() 으로 완료를 기다릴 수 있다.
    """
    stage_list = list(stages)
    thread = threading.Thread(
        target=execute_stages,
        args=(store, job_id, stage_list, context, start_index),
        daemon=True,
    )
    thread.start()
    return thread


def sse_format(event: dict) -> str:
    """이벤트 항목을 SSE 와이어 문자열로 직렬화한다.

    형식(02-architecture.md §4.1):
        event: <name>\\n
        data: <json>\\n
        \\n

    event 이름 규칙(간단·문서화):
      - 이벤트의 "message" 값이 알려진 라이프사이클 타입
        (stage_started/stage_done/job_done/error)이면 그 값을 SSE event 이름으로 쓴다.
      - 그 외에는 "message" 로 둔다.
    data 페이로드는 stage/payload 등 이벤트의 의미 있는 필드를 담은 JSON 객체다.
    """
    message = event.get("message")
    name = message if message in _SSE_EVENT_NAMES else "message"

    data = {
        "stage": event.get("stage"),
        "message": message,
        "level": event.get("level"),
        "ts": event.get("ts"),
    }
    payload = event.get("payload")
    if isinstance(payload, dict):
        # payload 키를 data 에 평탄화(stage 등 기존 키는 덮어쓰지 않음)
        for k, v in payload.items():
            data.setdefault(k, v)
    elif payload is not None:
        data["payload"] = payload

    body = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return f"event: {name}\ndata: {body}\n\n"
