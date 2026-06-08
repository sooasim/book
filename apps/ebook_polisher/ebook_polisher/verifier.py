"""검증기 (Verifier).

청크 계획 무손실성, 윤문 출력 보존성, 숫자/토큰 보존을 검증한다.
원칙(docs/07): AI 출력은 자유 문장이 아니라 block_id·숫자를 보존하는 계약이다.
"""
from __future__ import annotations

import re
from collections import Counter

from ebook_polisher.models import Chunk

# 보존해야 하는 시퀀스 추출용 정규식.
_NUMBER_RE = re.compile(r"\d[\d.,]*")
_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_ISBN_RE = re.compile(r"\b(?:ISBN[-\s]?(?:13|10)?:?\s?)?(?:97[89][-\s]?)?\d{1,5}[-\s]?\d+[-\s]?\d+[-\s]?[\dxX]\b")
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,}\b")


def verify_chunk_plan(all_block_ids: list[str], chunks: list[Chunk]) -> dict:
    """청크 계획의 무손실성 검증.

    ok 가 되려면 누락 없음, 중복 primary 없음, overlap-only 없음.
    """
    primary: list[str] = []
    overlap: list[str] = []
    for chunk in chunks:
        primary.extend(chunk.primary_block_ids)
        overlap.extend(chunk.overlap_block_ids)
    primary_count = Counter(primary)
    all_set = set(all_block_ids)
    primary_set = set(primary)
    missing = sorted(all_set - primary_set)
    duplicate_primary = sorted([bid for bid, n in primary_count.items() if n > 1])
    # overlap 에는 있으나 어떤 primary 에도 없는 블록.
    overlap_only = sorted((all_set & set(overlap)) - primary_set)
    return {
        "ok": not missing and not duplicate_primary and not overlap_only,
        "missing": missing,
        "duplicate_primary": duplicate_primary,
        "overlap_only": overlap_only,
        "coverage_ratio": len(primary_set & all_set) / max(1, len(all_set)),
    }


def verify_polished_blocks(
    source_block_ids: list[str], output_block_ids: list[str]
) -> dict:
    """입력 block_id 마다 정확히 하나의 출력이 있는지 검증."""
    missing = sorted(set(source_block_ids) - set(output_block_ids))
    extra = sorted(set(output_block_ids) - set(source_block_ids))
    return {"ok": not missing and not extra, "missing": missing, "extra": extra}


def _extract_numbers(text: str) -> list[str]:
    return _NUMBER_RE.findall(text or "")


def _extract_tokens(text: str) -> list[str]:
    """보존해야 하는 비숫자 토큰: URL, ISBN-유사, 대문자 약어."""
    text = text or ""
    tokens: list[str] = []
    tokens.extend(_URL_RE.findall(text))
    tokens.extend(_ISBN_RE.findall(text))
    tokens.extend(_ACRONYM_RE.findall(text))
    return tokens


def preserve_check(raw_text: str, polished_text: str) -> dict:
    """숫자·보존토큰·길이비 점검.

    ok=True 조건: raw 의 모든 숫자가 polished 에 (다중집합 기준) 존재하고
    length_ratio = len(polished)/len(raw) >= 0.5.
    """
    raw_numbers = Counter(_extract_numbers(raw_text))
    pol_numbers = Counter(_extract_numbers(polished_text))
    # raw 에 있으나 polished 가 충분히 담지 못한 숫자(다중집합 차집합).
    missing_numbers_counter = raw_numbers - pol_numbers
    missing_numbers = sorted(missing_numbers_counter.elements())

    raw_tokens = Counter(_extract_tokens(raw_text))
    pol_tokens = Counter(_extract_tokens(polished_text))
    missing_tokens_counter = raw_tokens - pol_tokens
    missing_tokens = sorted(missing_tokens_counter.elements())

    raw_len = len(raw_text or "")
    length_ratio = (len(polished_text or "") / raw_len) if raw_len else 1.0

    ok = (not missing_numbers) and (length_ratio >= 0.5)
    return {
        "ok": ok,
        "missing_numbers": missing_numbers,
        "missing_tokens": missing_tokens,
        "length_ratio": length_ratio,
    }


def forbidden_change_report(
    raw: str, polished: str, forbidden_types: list[str]
) -> dict:
    """금지 변경 보고. 최소한 'number' 보존을 preserve_check 로 점검."""
    violations: list[dict] = []
    check = preserve_check(raw, polished)
    if "number" in (forbidden_types or []):
        if check["missing_numbers"]:
            violations.append(
                {
                    "type": "number",
                    "detail": "원문 숫자가 윤문에서 누락/변경됨",
                    "missing": check["missing_numbers"],
                }
            )
        if check["length_ratio"] < 0.5:
            violations.append(
                {
                    "type": "length",
                    "detail": "윤문 길이가 원문의 50% 미만",
                    "length_ratio": check["length_ratio"],
                }
            )
    return {"ok": not violations, "violations": violations}
