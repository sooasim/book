"""7-Agency 규칙 기반 토론(debate) — 결정적, LLM 없음.

에이전시 역할:
  A, B, C : 논리/사실 검증(플레이스홀더 체크).
  E       : 정직성 / 정직 봉인(honest-boxing).
  F       : 축약(condense).
  G       : 편집자(editor) — 윤문 제안 생성.
  J       : 임원(executive) — 린트/리스크 판정.

run_agency_debate 는 polisher 와 lint_fn 을 주입(DI)받아 결정적이고
부작용 없이 PolishResult 를 (가능하면 주석을 달아) 반환한다.
"""
from __future__ import annotations

from typing import Callable

from ebook_polisher.models import PolishResult


# --------------------------------------------------------------------------- 역할 상수
AGENCY_ROLES = ("A", "B", "C", "E", "F", "G", "J")


# --------------------------------------------------------------------------- 개별 역할 헬퍼
def _agent_e_honesty(result: PolishResult) -> None:
    """E: 경고가 있거나 모호한 블록은 정직 봉인 마커를 'crescent' 로 설정한다."""
    for block in result.polished_blocks:
        if block.warnings:
            block.honest_marker = "crescent"
        # 경고가 없으면 기존 마커를 유지한다(기본 'star').


def _agent_j_lint(result: PolishResult, lint_fn: Callable[[str], bool]) -> None:
    """J: 각 블록의 윤문 텍스트에 린트를 적용. 실패 시 리스크 플래그를 추가한다."""
    for block in result.polished_blocks:
        ok = lint_fn(block.polished_text)
        if not ok:
            flag = f"hardfail:{block.block_id}"
            if flag not in result.risk_flags:
                result.risk_flags.append(flag)


# --------------------------------------------------------------------------- 토론 진입점
def run_agency_debate(
    payload: dict,
    polisher,
    lint_fn: Callable[[str], bool],
) -> PolishResult:
    """규칙 기반 에이전시 토론을 실행하고 (주석된) PolishResult 를 반환한다.

    1) G: polisher.polish(payload) 로 편집 제안(PolishResult)을 얻는다.
    2) E: 경고/모호성이 있는 블록에 정직 봉인 마커('crescent')를 보장한다.
    3) J: 각 윤문 텍스트에 lint_fn 을 실행, 실패 시 리스크 플래그를 추가한다(크래시 금지).
    """
    # 1) 편집자(G) — 윤문 제안 생성.
    result = polisher.polish(payload)

    # 2) 정직성(E) — 정직 봉인.
    _agent_e_honesty(result)

    # 3) 임원(J) — 린트/리스크 판정.
    _agent_j_lint(result, lint_fn)

    return result
