"""규칙 기반 윤문기(RulesPolisher) — 무손실 결정론 클린업.

Polisher 프로토콜 구현. 청크 페이로드를 받아 각 source block마다 정확히
하나의 PolishedBlock을 반환한다(block_id 보존이 핵심 계약).

윤문은 의미·숫자·고유명사·문장부호를 절대 바꾸지 않는, 무손실(lossless)
서식 정리만 수행한다:
  - 연속된 공백/탭을 단일 공백으로 축약
  - 줄 끝 공백 제거
  - 3개 이상 연속 개행을 2개로 축약
"""
from __future__ import annotations

import re

from ebook_polisher.models import PolishResult, PolishedBlock

# 불확실성 신호어: 있으면 ◑(crescent) 정직 봉인 마커를 부여.
AMBIGUITY_SIGNALS = ["추정", "아마도", "불명확", "모호"]

# 숫자 인접 불확실 표현(숫자 옆에 어림/추정 어휘가 붙는 경우).
_UNCERTAIN_NEAR_NUMBER = re.compile(
    r"\d[^\n]{0,6}(?:쯤|가량|정도|약|여|내외|추정)"
    r"|(?:약|대략|얼추)[^\n]{0,6}\d"
)


def _clean_text(text: str) -> str:
    """무손실 서식 정리. 의미/숫자/부호는 보존한다."""
    if text is None:
        return ""
    # 줄 단위로 처리: 줄 안의 공백/탭만 축약, 줄 끝 공백 제거.
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        # 연속된 공백/탭(개행 제외)을 단일 공백으로 축약.
        line = re.sub(r"[ \t]+", " ", line)
        # 줄 끝 공백 제거.
        line = line.rstrip(" \t")
        cleaned_lines.append(line)
    result = "\n".join(cleaned_lines)
    # 3개 이상 연속 개행을 2개로 축약.
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


def _honest_marker(text: str) -> str:
    """불확실성 신호가 있으면 'crescent', 아니면 'star'."""
    if any(sig in text for sig in AMBIGUITY_SIGNALS):
        return "crescent"
    if _UNCERTAIN_NEAR_NUMBER.search(text):
        return "crescent"
    return "star"


def _polish_one(block: dict) -> PolishedBlock:
    block_id = block.get("block_id", "")
    text = block.get("text", "") or ""
    polished = _clean_text(text)
    change_level = "none" if polished == text else "light"
    marker = _honest_marker(text)
    return PolishedBlock(
        block_id=block_id,
        polished_text=polished,
        change_level=change_level,
        honest_marker=marker,
    )


class RulesPolisher:
    """규칙 기반 윤문기. Polisher 프로토콜을 만족한다."""

    def polish(self, payload: dict, style_bible: str = "") -> PolishResult:
        chunk_id = payload.get("chunk_id", "")
        source_blocks = payload.get("source_blocks", []) or []
        polished_blocks = [_polish_one(b) for b in source_blocks]
        return PolishResult(chunk_id=chunk_id, polished_blocks=polished_blocks)

    def polish_blocks(self, blocks: list, chunk_id: str = "") -> PolishResult:
        """편의 메서드: source_blocks 리스트만으로 윤문한다."""
        return self.polish({"chunk_id": chunk_id, "source_blocks": blocks})
