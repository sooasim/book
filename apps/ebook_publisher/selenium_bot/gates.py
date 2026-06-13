"""사람 확인 게이트(HUMAN GATE) 안전 코어.

이 모듈은 동결 계약(models.py)의 HUMAN_GATES / AUTOMATABLE_ACTIONS 에 의존하여
"위험 단계는 절대 자동 실행되지 않는다"는 안전 경계를 코드로 강제한다.

순수 함수로 구성되며 결정적(deterministic)이다. 표준 라이브러리만 사용한다.
"""
from __future__ import annotations

from . import models

# HUMAN_GATES 각 항목에 대한 사람이 읽을 한국어 라벨.
_GATE_LABELS: dict[str, str] = {
    "account_create_final": "회원가입 최종 완료",
    "captcha": "캡차",
    "email_verify": "이메일 인증",
    "phone_verify": "휴대폰 본인인증",
    "identity_verify": "신원/사업자 인증",
    "tos_agree": "약관 동의",
    "content_rights_confirm": "저작권/출판권 확인",
    "ai_disclosure": "AI 사용 고지",
    "exclusivity": "독점 계약",
    "tax_info": "세금 정보",
    "payout_info": "정산 계좌",
    "pricing_confirm": "가격 확정",
    "final_submit": "최종 게시",
}


class HumanGateError(RuntimeError):
    """사람만 수행해야 하는 단계를 자동으로 통과하려 할 때 발생."""


def is_human_gate(name: str) -> bool:
    """주어진 이름이 사람 확인 게이트면 True."""
    return name in models.HUMAN_GATES


def assert_not_automatable(action_or_gate: str) -> None:
    """사람 확인 게이트면 HumanGateError 를 발생시킨다. 그 외에는 no-op.

    호출 코드가 사람 전용 단계를 자동화하려 한 경우를 차단한다.
    """
    if is_human_gate(action_or_gate):
        raise HumanGateError(
            f"'{action_or_gate}' 는 사람 확인 게이트이므로 자동화할 수 없습니다."
        )


def guard_action(action: str) -> None:
    """알려진 안전 액션 또는 명시적 'human_gate' 마커만 허용한다.

    그 외(미지/위험 액션)는 HumanGateError 를 발생시킨다.
    """
    if action in models.AUTOMATABLE_ACTIONS or action == "human_gate":
        return
    raise HumanGateError(
        f"'{action}' 는 허용되지 않은 액션입니다(자동화 가능 액션 또는 human_gate 만 허용)."
    )


def gate_label(gate: str) -> str:
    """게이트의 사람이 읽을 한국어 라벨. 미지의 이름은 원본을 그대로 반환."""
    return _GATE_LABELS.get(gate, gate)


def human_checklist(gates: list[str]) -> list[dict]:
    """각 게이트에 대한 체크리스트 항목 목록을 반환한다.

    [{"gate", "label", "done": False}, ...] 형태이며, 순서를 보존하고
    중복은 제거한다.
    """
    seen: set[str] = set()
    checklist: list[dict] = []
    for gate in gates:
        if gate in seen:
            continue
        seen.add(gate)
        checklist.append({"gate": gate, "label": gate_label(gate), "done": False})
    return checklist
