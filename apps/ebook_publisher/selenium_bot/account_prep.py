"""계정 가입 계획(SignupProfile -> PublishPlan) 빌더 — 순수 함수.

가입 폼의 **비위험 필드만** 자동으로 채우는 계획을 만든다. 비밀번호·세금·
정산 계좌·캡차·최종 "계정 만들기" 버튼은 절대 자동화하지 않고 human_gate 로만
표시한다.

네트워크/Selenium 의존 없음. 전부 결정적(deterministic) 순수 함수.
"""
from __future__ import annotations

import datetime

from selenium_bot.models import (
    HUMAN_GATES,
    PlanStep,
    PlatformSite,
    PublishPlan,
    SignupProfile,
)

_VALID_HUMAN_GATES: frozenset[str] = frozenset(HUMAN_GATES)

# (profile 속성, 폼 field_key, 라벨) — 채움 단계 순서 고정.
_PROFILE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("display_name", "display_name", "표시 이름"),
    ("email", "email", "이메일"),
    ("pen_name", "pen_name", "필명"),
    ("country", "country", "국가"),
)

# 사이트가 요구할 수 있는 가입 관련 게이트(고정 순서). account_create_final 은
# 항상 마지막에 들어가므로 여기에는 포함하지 않는다.
_SIGNUP_GATE_ORDER: tuple[str, ...] = (
    "captcha",
    "email_verify",
    "phone_verify",
    "identity_verify",
    "tos_agree",
)

# 자동화로 절대 채우지 않는 민감 field_key(방어적 차단 목록).
_FORBIDDEN_FIELD_KEYS: frozenset[str] = frozenset(
    {"password", "tax", "payout", "ssn", "card", "captcha"}
)


def _utc_now_iso() -> str:
    """현재 UTC 시각을 ISO 8601 문자열로 반환한다."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def signup_human_gates(site: PlatformSite) -> list[str]:
    """가입 관련 사람 확인 게이트의 정렬된 부분집합을 반환한다.

    사이트가 요구하는 captcha/email_verify/phone_verify/identity_verify/
    tos_agree 를 고정 순서로 추리고, 항상 마지막에 account_create_final 을 둔다.
    """
    site_gates = set(site.human_gates or [])
    gates = [g for g in _SIGNUP_GATE_ORDER if g in site_gates]
    gates.append("account_create_final")
    return gates


def build_signup_plan(profile: SignupProfile, site: PlatformSite) -> PublishPlan:
    """가입 프로필 + 사이트로부터 가입 계획을 만든다(book_id="").

    단계 순서:
      1. open_url (signup_url 우선, 없으면 primary_url)
      2. 비어 있지 않은 프로필 필드별 fill 단계
         (display_name, email, pen_name, country)
      3. 가입 관련 human_gate 단계(항상 account_create_final 포함)

    비밀번호·세금·정산·캡차·최종 계정생성 버튼은 자동 채움/클릭하지 않는다.
    """
    steps: list[PlanStep] = []

    # 1. 가입 페이지 열기
    open_target = site.signup_url or site.primary_url
    steps.append(
        PlanStep(action="open_url", value=open_target, note="가입 페이지 열기")
    )

    # 2. 프로필 채움 단계(비어 있지 않은 필드만, 금지 키 제외)
    for attr, field_key, label in _PROFILE_FIELDS:
        if field_key in _FORBIDDEN_FIELD_KEYS:
            continue
        value = (getattr(profile, attr, "") or "").strip()
        if not value:
            continue
        steps.append(
            PlanStep(
                action="fill",
                field_key=field_key,
                value=value,
                note=label,
            )
        )

    # 3. 가입 관련 human_gate 단계(항상 account_create_final 포함)
    for gate in signup_human_gates(site):
        steps.append(
            PlanStep(
                action="human_gate",
                gate=gate,
                human=True,
                note=f"사람 확인 필요: {gate}",
            )
        )

    return PublishPlan(
        platform_id=site.platform_id,
        book_id="",
        steps=steps,
        created_at=_utc_now_iso(),
    )
