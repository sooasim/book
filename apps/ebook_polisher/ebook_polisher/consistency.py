"""일관성 패스 (Consistency Pass — docs/07 §9).

대형 원고에서 사람이 잡기 어려운 두 종류의 비일관성을 결정론적으로 탐지한다.
  1) 경어체 표류(honorific drift): 문장 종결 어미가 책 전체의 지배적 문체에서 벗어나는 경우.
  2) 용어 변형(term variants): 용어집 위반 + 띄어쓰기만 다른 동일 용어의 자동 군집.

정직 봉인 철학에 따라 이 모듈은 텍스트를 고치지 않고 '리포트'만 한다.
순수·결정론 함수로 구성되며 표준 라이브러리만 사용한다.
"""
from __future__ import annotations

import re

from ebook_polisher.models import Block


# --------------------------------------------------------------------------- 종결 어미 분류
# 종결 어미 판정 시 제거할 후행 문장부호/따옴표.
_TRAILING = " \t\r\n.!?…\"'”’」』）) "


def _strip_ending(sentence: str) -> str:
    """종결 어미 판정을 위해 후행 문장부호·따옴표·공백을 제거한다."""
    return (sentence or "").strip().rstrip(_TRAILING).strip()


def classify_ending(sentence: str) -> str:
    """문장 종결 어미를 'formal' | 'polite' | 'plain' | 'other' 로 분류한다."""
    s = _strip_ending(sentence)
    if not s:
        return "other"

    # formal: 합쇼체(격식체). "입니다"처럼 ㅂ받침이 합쳐진 형태(…니다/…니까)도 포함.
    if s.endswith(("습니다", "ㅂ니다", "습니까", "ㅂ니까", "니다", "니까")):
        return "formal"

    # polite: 해요체(비격식 높임)
    if s.endswith(("어요", "예요", "에요", "아요", "여요")) or s.endswith("요"):
        return "polite"

    # plain: 해라체/평서체
    if s.endswith(("었다", "였다", "는다", "ㄴ다", "이다", "다")):
        return "plain"

    return "other"


# --------------------------------------------------------------------------- 문장 분할
# 종결 어미(다/요) 뒤의 마침표, 또는 일반 문장부호(.!?) 경계에서 분할한다.
# 간결·결정론을 위해 어미+구두점 경계만 본다.
_SENT_SPLIT = re.compile(r"(?<=[다요])[.!?]+|[.!?]+")


def _split_sentences(text: str) -> list[str]:
    """문단 텍스트를 문장 리스트로 분할한다(빈 조각 제외)."""
    if not text:
        return []
    parts = _SENT_SPLIT.split(text)
    return [p.strip() for p in parts if p and p.strip()]


def _prose_blocks(blocks) -> list[Block]:
    return [b for b in blocks if b.block_type == "paragraph"]


def _block_text(block: Block) -> str:
    return block.polished_text or block.text


# --------------------------------------------------------------------------- 경어체 표류
def detect_honorific_drift(blocks) -> dict:
    """문단 블록의 종결 문체를 분석해 지배 문체에서 벗어난 블록을 보고한다.

    반환: {"dominant", "counts", "deviating_block_ids", "ok"}.
    ok = 벗어난 블록 비율 < 0.2 (또는 산문 블록 없음).
    """
    prose = _prose_blocks(blocks)
    counts: dict[str, int] = {"formal": 0, "polite": 0, "plain": 0, "other": 0}

    # 블록별 등장 문체 집합(other 제외) 기록.
    block_styles: list[tuple[str, set[str]]] = []
    for b in prose:
        styles: set[str] = set()
        for sent in _split_sentences(_block_text(b)):
            style = classify_ending(sent)
            counts[style] += 1
            if style != "other":
                styles.add(style)
        block_styles.append((b.block_id, styles))

    # 지배 문체 결정: other 제외하고 최다. 결정론을 위해 (count, style) 정렬.
    ranked = sorted(
        ((c, s) for s, c in counts.items() if s != "other" and c > 0),
        key=lambda x: (-x[0], x[1]),
    )
    dominant = ranked[0][1] if ranked else "other"

    deviating_block_ids = [
        bid
        for bid, styles in block_styles
        if styles and any(st != dominant for st in styles)
    ]

    total = len(prose)
    ratio = (len(deviating_block_ids) / total) if total else 0.0
    # 비율이 0.2를 넘을 때만 비일관(부동소수 경계 1/5=0.2는 ok로 본다).
    ok = total == 0 or ratio <= 0.2

    return {
        "dominant": dominant,
        "counts": counts,
        "deviating_block_ids": deviating_block_ids,
        "ok": ok,
    }


# --------------------------------------------------------------------------- 용어 변형
def _normalize_spaces(token: str) -> str:
    """공백을 모두 제거한 정규형(띄어쓰기 변형 비교용)."""
    return re.sub(r"\s+", "", token)


# 한글/영문/숫자로 이루어진 단어 토큰. 조사 등을 떼기 위해 한글은 별도 처리하지 않고
# 단어 단위로 본 뒤, 연속 단어 n-gram을 만들어 띄어쓰기 변형을 비교한다.
_WORD_RE = re.compile(r"[0-9A-Za-z가-힣]+")

# 띄어쓰기 변형 비교 시 묶을 최대 연속 단어 수.
_MAX_NGRAM = 4


def _span_forms(text: str):
    """텍스트에서 (정규형key, 원표기form) 후보를 생성한다.

    연속한 1..N개 단어를 공백으로 이어 붙인 표기와, 공백을 제거한 정규형을 함께 낸다.
    "리만가설"(한 단어)과 "리만 가설"(두 단어)이 같은 정규형 "리만가설"으로 묶인다.
    """
    words = _WORD_RE.findall(text)
    n = len(words)
    for i in range(n):
        for size in range(1, _MAX_NGRAM + 1):
            if i + size > n:
                break
            form = " ".join(words[i : i + size])
            key = _normalize_spaces(form)
            yield key, form


def detect_term_variants(blocks, glossary: dict | None = None) -> dict:
    """용어집 위반과 띄어쓰기 변형 군집을 탐지한다.

    반환: {"violations", "variant_clusters", "ok"}.
    ok = 용어집 위반이 없을 때 True.
    """
    glossary = glossary or {}

    # --- 1) 용어집 위반: 정규 용어가 아닌 변형 표기를 찾는다.
    violations: list[dict] = []
    for canonical, variants in glossary.items():
        for b in blocks:
            text = _block_text(b)
            for variant in variants:
                if variant and variant != canonical and variant in text:
                    violations.append(
                        {
                            "block_id": b.block_id,
                            "found": variant,
                            "canonical": canonical,
                        }
                    )

    # --- 2) 자동 띄어쓰기 변형 군집.
    # 공백 제거 후 동일하지만 실제 표기 형태가 2종 이상이면 군집으로 보고.
    # 연속 1..N 단어 n-gram을 만들어 "리만가설"(한 단어)과 "리만 가설"(두 단어)을
    # 같은 정규형 키 아래로 묶는다.
    norm_to_forms: dict[str, dict] = {}
    for b in blocks:
        text = _block_text(b)
        for key, form in _span_forms(text):
            # 단일 글자 등 너무 짧은 정규형은 잡음이므로 제외.
            if len(key) < 2:
                continue
            entry = norm_to_forms.setdefault(key, {"forms": set(), "block_ids": set()})
            entry["forms"].add(form)
            entry["block_ids"].add(b.block_id)

    variant_clusters: list[dict] = []
    for key, entry in norm_to_forms.items():
        if len(entry["forms"]) >= 2:
            variant_clusters.append(
                {
                    "key": key,
                    "forms": sorted(entry["forms"]),
                    "block_ids": sorted(entry["block_ids"]),
                }
            )
    variant_clusters.sort(key=lambda c: c["key"])

    return {
        "violations": violations,
        "variant_clusters": variant_clusters,
        "ok": not violations,
    }


# --------------------------------------------------------------------------- 통합 리포트
def consistency_report(blocks, glossary=None) -> dict:
    """경어체·용어 일관성 검사를 통합한다."""
    honorific = detect_honorific_drift(blocks)
    terminology = detect_term_variants(blocks, glossary)
    return {
        "ok": bool(honorific["ok"] and terminology["ok"]),
        "honorific": honorific,
        "terminology": terminology,
    }
