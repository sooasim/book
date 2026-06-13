"""게시 계획(PublishPlan) 빌더 — 순수 함수, 표준 라이브러리만 사용.

브라우저를 띄우지 않고, 책 메타데이터와 PlatformSite 로부터 **단계 계획**만
만든다. 위험 단계(최종 게시·캡차·세금/정산 등)는 human_gate 로 표시하여
사람이 직접 수행하게 한다(절대 자동 통과하지 않음).

네트워크/Selenium 의존 없음. 전부 결정적(deterministic) 순수 함수.
"""
from __future__ import annotations

import dataclasses
import datetime
import json

from selenium_bot.models import (
    HUMAN_GATES,
    PlanStep,
    PlatformSite,
    PublishPlan,
)

_VALID_HUMAN_GATES: frozenset[str] = frozenset(HUMAN_GATES)

# (book 키, 폼 field_key, 사람이 읽을 라벨) — 채움 단계 순서를 고정한다.
_METADATA_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("title", "title", "제목"),
    ("subtitle", "subtitle", "부제"),
    ("author", "author", "저자"),
    ("description", "description", "설명"),
    ("keywords", "keywords", "키워드"),
    ("categories", "categories", "카테고리"),
    ("language", "language", "언어"),
    ("isbn_ebook", "isbn", "ISBN"),
)


def _utc_now_iso() -> str:
    """현재 UTC 시각을 ISO 8601 문자열로 반환한다."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _stringify(value) -> str:
    """폼에 넣을 값을 문자열로 정규화한다(리스트는 ', ' 결합)."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(part) for part in value)
    return str(value)


def build_publish_plan(
    book: dict,
    site: PlatformSite,
    files: dict | None = None,
) -> PublishPlan:
    """책 메타데이터 + 사이트로부터 순서가 고정된 게시 계획을 만든다.

    단계 순서:
      1. open_url (플랫폼 열기)
      2. wait_human_login (사람이 직접 로그인; human=True)
      3. 존재하는 메타데이터 필드별 fill 단계
      4. 업로드 단계(원고/EPUB, 표지)
      5. price fill (price_usd 우선, 없으면 price_krw)
      6. site.human_gates 각각에 대한 human_gate 단계
         — 항상 "final_submit" 이 마지막 단계가 되도록 보장한다.
    """
    book = book or {}
    files = files or {}
    steps: list[PlanStep] = []

    # 1. 플랫폼 열기
    steps.append(
        PlanStep(action="open_url", value=site.primary_url, note="플랫폼 열기")
    )

    # 2. 사람이 직접 로그인(없으면 가입 먼저)
    steps.append(
        PlanStep(
            action="wait_human_login",
            human=True,
            note="사람이 직접 로그인(없으면 가입 먼저)",
        )
    )

    # 3. 메타데이터 채움 단계(존재하는 필드만)
    for book_key, field_key, label in _METADATA_FIELDS:
        if book_key not in book:
            continue
        text = _stringify(book.get(book_key))
        if text == "":
            continue
        steps.append(
            PlanStep(
                action="fill",
                field_key=field_key,
                value=text,
                note=label,
            )
        )

    # 4. 업로드 단계(원고/EPUB, 표지)
    manuscript = files.get("epub") or files.get("manuscript")
    if manuscript:
        steps.append(
            PlanStep(
                action="upload",
                field_key="manuscript_file",
                value=_stringify(manuscript),
                note="원고/EPUB 업로드",
            )
        )
    cover = files.get("cover")
    if cover:
        steps.append(
            PlanStep(
                action="upload",
                field_key="cover_file",
                value=_stringify(cover),
                note="표지 업로드",
            )
        )

    # 5. 가격(price_usd 우선, 없으면 price_krw)
    price_value = ""
    if book.get("price_usd") not in (None, ""):
        price_value = _stringify(book.get("price_usd"))
    elif book.get("price_krw") not in (None, ""):
        price_value = _stringify(book.get("price_krw"))
    if price_value != "":
        steps.append(
            PlanStep(
                action="fill",
                field_key="price",
                value=price_value,
                note="가격 입력",
            )
        )

    # 6. human_gate 단계 — site.human_gates 순서대로, 단 final_submit 은 마지막.
    gates: list[str] = [g for g in site.human_gates if g != "final_submit"]
    for gate in gates:
        steps.append(_human_gate_step(gate))
    steps.append(_human_gate_step("final_submit"))

    return PublishPlan(
        platform_id=site.platform_id,
        book_id=_stringify(book.get("book_id")),
        steps=steps,
        created_at=_utc_now_iso(),
    )


def _human_gate_step(gate: str) -> PlanStep:
    """human_gate 단계 한 건을 만든다(human=True 강제)."""
    return PlanStep(
        action="human_gate",
        gate=gate,
        human=True,
        note=f"사람 확인 필요: {gate}",
    )


def plan_to_dict(plan: PublishPlan) -> dict:
    """PublishPlan(중첩 dataclass 포함)을 순수 dict 로 직렬화한다."""
    return dataclasses.asdict(plan)


def plan_to_json(plan: PublishPlan) -> str:
    """PublishPlan 을 JSON 문자열로 직렬화한다(비밀번호 등 민감값 없음)."""
    return json.dumps(plan_to_dict(plan), ensure_ascii=False, sort_keys=True)


def auto_steps(plan: PublishPlan) -> list[PlanStep]:
    """자동화 가능한 단계(human_gate 아님)만 반환한다."""
    return [s for s in plan.steps if s.action != "human_gate"]


def human_steps(plan: PublishPlan) -> list[PlanStep]:
    """사람이 직접 해야 하는 단계(human_gate 또는 human=True)만 반환한다."""
    return [s for s in plan.steps if s.action == "human_gate" or s.human]


def assert_plan_invariants(plan: PublishPlan) -> None:
    """계획의 안전 불변식을 검증한다(위반 시 ValueError).

    - action=="human_gate" 인 단계는 human=True 이고 gate 가 HUMAN_GATES 에 속한다.
    - 자동화 가능 단계는 human_gate 를 달고 있지 않다(gate 비어 있음).
    - 마지막 단계는 action=="human_gate" 이고 gate=="final_submit".
    """
    if not plan.steps:
        raise ValueError("plan has no steps")

    for step in plan.steps:
        if step.action == "human_gate":
            if not step.human:
                raise ValueError(
                    f"human_gate step must have human=True (gate={step.gate!r})"
                )
            if step.gate not in _VALID_HUMAN_GATES:
                raise ValueError(f"unknown human gate: {step.gate!r}")
        else:
            if step.gate:
                raise ValueError(
                    f"automatable step {step.action!r} must not carry a gate "
                    f"(got {step.gate!r})"
                )

    last = plan.steps[-1]
    if last.action != "human_gate" or last.gate != "final_submit":
        raise ValueError("final step must be human_gate final_submit")
