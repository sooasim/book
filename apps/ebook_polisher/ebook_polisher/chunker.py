"""청크 계획기 (Chunker).

블록 목록을 토큰 한계 내의 작업 단위(청크)로 묶는다.
불변식: 모든 block_id 는 정확히 하나의 chunk.primary_block_ids 에 등장한다.
오버랩 블록은 직전 청크 꼬리에서 복제되어 다음 청크의 primary 로 이어진다.
"""
from __future__ import annotations

from ebook_polisher.models import Block, Chunk


def estimate_tokens(text: str) -> int:
    """토큰 수 추정. 결정론적: 문자수의 절반(최소 1)."""
    return max(1, len(text) // 2)


def tail_overlap(blocks: list[Block], overlap_tokens: int) -> list[Block]:
    """끝에서부터 오버랩 토큰 예산을 채울 때까지 블록을 모은다."""
    total = 0
    selected: list[Block] = []
    for block in reversed(blocks):
        total += estimate_tokens(block.text)
        selected.append(block)
        if total >= overlap_tokens:
            break
    return list(reversed(selected))


def boundary_score(block: Block) -> float:
    """경계 점수 (docs/07 §6 가중치).

    0.30*heading + 0.20*page + 0.20*semantic_shift
      + 0.15*para_balance + 0.10*scene - 0.05*table_formula_penalty.
    semantic_shift / scene 은 결정론 유지를 위해 0 placeholder.
    """
    heading = 1.0 if block.block_type == "title" else 0.0
    page = 1.0 if block.order_index == 0 else 0.0
    semantic_shift = 0.0
    para_balance = 1.0 if block.block_type == "paragraph" else 0.0
    scene = 0.0
    table_formula_penalty = 1.0 if block.block_type in ("table", "formula") else 0.0
    return (
        0.30 * heading
        + 0.20 * page
        + 0.20 * semantic_shift
        + 0.15 * para_balance
        + 0.10 * scene
        - 0.05 * table_formula_penalty
    )


def _page_num(page_id: str) -> int:
    """page_id 가 'pNNNNNN' 형태라고 가정하고 정수 페이지 번호를 추출."""
    return int(page_id[1:])


def plan_chunks(
    blocks: list[Block], max_tokens: int = 12000, overlap_tokens: int = 800
) -> list[Chunk]:
    """블록을 청크로 계획한다.

    불변식: 모든 block_id 가 정확히 하나의 chunk.primary_block_ids 에 등장.
    오버랩 블록은 직전 청크의 overlap_block_ids 에 기록되고, 다음 청크의
    primary 로 이어져(복제) primary 로서 정확히 한 번 등장하게 된다.
    """
    chunks: list[Chunk] = []
    current: list[Block] = []
    current_tokens = 0
    seq = 1
    for block in blocks:
        cost = estimate_tokens(block.text)
        if current and current_tokens + cost > max_tokens:
            overlap = tail_overlap(current, overlap_tokens)
            # 직전 청크의 primary 에서 오버랩 블록을 제외하여 중복 primary 방지.
            overlap_ids = {b.block_id for b in overlap}
            primary = [b for b in current if b.block_id not in overlap_ids]
            if not primary:
                # 오버랩이 청크 전체를 삼키는 경우(작은 청크) 오버랩을 비운다.
                primary = list(current)
                overlap = []
                overlap_ids = set()
            chunks.append(
                Chunk(
                    chunk_id=f"chunk_{seq:06d}",
                    primary_block_ids=[b.block_id for b in primary],
                    overlap_block_ids=[b.block_id for b in overlap],
                    page_start=_page_num(current[0].page_id),
                    page_end=_page_num(current[-1].page_id),
                    token_estimate=current_tokens,
                )
            )
            seq += 1
            current = list(overlap)
            current_tokens = sum(estimate_tokens(b.text) for b in current)
        current.append(block)
        current_tokens += cost
    if current:
        chunks.append(
            Chunk(
                chunk_id=f"chunk_{seq:06d}",
                primary_block_ids=[b.block_id for b in current],
                overlap_block_ids=[],
                page_start=_page_num(current[0].page_id),
                page_end=_page_num(current[-1].page_id),
                token_estimate=current_tokens,
            )
        )
    return chunks
