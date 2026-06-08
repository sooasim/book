"""프롬프트 구성 및 프롬프트 유전자(PromptGene) 선택.

POLISH_SYSTEM_PROMPT: 윤문 시스템 프롬프트(한국어, 편집자 역할).
build_user_prompt: 스타일 바이블 + 청크 페이로드 → 사용자 프롬프트.
PromptGene / score_gene / select_prompt_genes: 토큰 예산 내 탐욕적 선택.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from ebook_polisher.models import StyleProfile  # noqa: F401  (계약 일관성용)

POLISH_SYSTEM_PROMPT = """당신은 한국어 전자책 전문 편집자입니다.

역할:
- 주어진 원고 블록을 자연스럽고 읽기 좋게 윤문(다듬기)합니다.
- 띄어쓰기, 오타, 문장 흐름을 개선하되 원문의 의미를 절대 바꾸지 않습니다.

반드시 보존해야 할 것 (절대 수정 금지):
- 숫자, 날짜, 수치
- 고유명사(인명, 지명, 상표 등)
- 인용 및 출처 표기, 각주 번호
- 수식, 코드, ISBN, URL

출력 계약:
- 입력으로 주어진 각 block_id 마다 정확히 하나의 윤문된 블록을 반환합니다.
- block_id 를 절대 변경하거나 누락하거나 새로 만들지 않습니다.
- 불확실하거나 주의가 필요한 변경에는 경고(warning)를 남깁니다.
"""


def build_user_prompt(style_bible: str, chunk_payload: dict) -> str:
    """스타일 바이블과 청크 페이로드로 사용자 프롬프트를 구성한다.

    style_bible 텍스트가 결과 문자열에 그대로 포함된다.
    """
    payload_json = json.dumps(chunk_payload, ensure_ascii=False, indent=2)
    return (
        "다음 스타일 바이블을 엄격히 준수하여 윤문하십시오.\n\n"
        f"{style_bible}\n\n"
        "[윤문 대상 청크]\n"
        f"{payload_json}\n\n"
        "각 block_id 에 대해 윤문된 블록을 정확히 하나씩 반환하십시오."
    )


@dataclass
class PromptGene:
    gene_id: str
    category: str
    content: str
    genre_match: float
    task_match: float
    success_rate: float
    token_efficiency: float
    recency: float
    token_cost: int


def score_gene(gene: PromptGene) -> float:
    return (
        0.35 * gene.genre_match
        + 0.25 * gene.task_match
        + 0.20 * gene.success_rate
        + 0.10 * gene.token_efficiency
        + 0.10 * gene.recency
    )


def select_prompt_genes(
    candidates: list[PromptGene], token_budget: int
) -> list[PromptGene]:
    """점수 내림차순으로 탐욕적으로 선택하되 토큰 예산을 초과하지 않는다."""
    selected: list[PromptGene] = []
    used = 0
    for gene in sorted(candidates, key=score_gene, reverse=True):
        if used + gene.token_cost <= token_budget:
            selected.append(gene)
            used += gene.token_cost
    return selected
