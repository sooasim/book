"""메모리 라우터 — 후보 메모리 매치를 점수화하여 상위 항목을 선택한다.

가중치:
  0.35 의미 유사도, 0.20 중요도, 0.15 최신성,
  0.15 챕터 관련성, 0.10 사용자 고정, 0.05 검증 신뢰도.
"""
from __future__ import annotations

from dataclasses import dataclass

from ebook_polisher.models import MemoryItem


@dataclass
class MemoryMatch:
    item: MemoryItem
    semantic_similarity: float
    recency: float
    chapter_relevance: float
    user_pinned: float = 0.0
    validation_confidence: float = 1.0


def memory_score(match: MemoryMatch) -> float:
    return (
        0.35 * match.semantic_similarity
        + 0.20 * match.item.importance
        + 0.15 * match.recency
        + 0.15 * match.chapter_relevance
        + 0.10 * match.user_pinned
        + 0.05 * match.validation_confidence
    )


def select_memory(matches: list[MemoryMatch], limit: int = 20) -> list[MemoryItem]:
    """점수 내림차순으로 정렬한 뒤 상위 limit 개의 MemoryItem 을 반환한다."""
    ranked = sorted(matches, key=memory_score, reverse=True)
    return [match.item for match in ranked[:limit]]
