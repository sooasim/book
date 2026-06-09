"""Style Bible (생성 지향 헬퍼).

OCES 03 §3.3 일관성 요구사항을 위한 상위 레벨 스타일 규칙 헬퍼.

`style_bible.py` (StyleProfile 기반 윤문 규칙) 과는 별개로, 생성 단계에서
독자층/톤/용어집을 받아 (a) 작성 프롬프트에 끼워넣을 수 있는 한국어 텍스트
블록과 (b) 용어 정규화·위반 검출 유틸을 제공한다.

모든 함수는 결정적이며 순수하다 (stdlib only).
"""
from __future__ import annotations

# 종결 어미 스타일 라벨. (이 모듈 고유의, 생성 지향 라벨)
_HONORIFIC_LABELS = {
    "plain": "평서체",
    "polite": "해요체",
    "formal": "하십시오체",
}


def build_style_bible(
    audience: str = "",
    tone: str = "",
    honorific: str = "plain",
    glossary: dict | None = None,
    length_target: int = 0,
    banned: list[str] | None = None,
) -> dict:
    """스타일 규칙을 담은 dict 를 구성한다.

    반환 키: audience, tone, honorific, glossary(canonical->variants),
    length_target, banned(list).
    """
    if honorific not in _HONORIFIC_LABELS:
        honorific = "plain"

    norm_glossary: dict[str, list[str]] = {}
    if glossary:
        for canonical, variants in glossary.items():
            if variants is None:
                norm_glossary[canonical] = []
            elif isinstance(variants, str):
                norm_glossary[canonical] = [variants]
            else:
                norm_glossary[canonical] = list(variants)

    return {
        "audience": audience or "",
        "tone": tone or "",
        "honorific": honorific,
        "glossary": norm_glossary,
        "length_target": int(length_target) if length_target else 0,
        "banned": list(banned) if banned else [],
    }


def render_style_bible(bible: dict) -> str:
    """스타일 규칙 dict 를 사람/LLM 이 읽을 수 있는 한국어 텍스트 블록으로 렌더링한다.

    빈 섹션은 생략한다. 이 문자열은 작성 프롬프트에 주입된다.
    """
    lines = ["[STYLE BIBLE]"]

    audience = bible.get("audience", "")
    if audience:
        lines.append(f"독자층: {audience}")

    tone = bible.get("tone", "")
    if tone:
        lines.append(f"톤: {tone}")

    honorific = bible.get("honorific", "")
    if honorific:
        label = _HONORIFIC_LABELS.get(honorific, honorific)
        lines.append(f"종결: {label}")

    glossary = bible.get("glossary") or {}
    if glossary:
        terms = []
        for canonical in glossary:
            variants = glossary[canonical]
            if variants:
                terms.append(f"{canonical}(={', '.join(variants)})")
            else:
                terms.append(canonical)
        lines.append(f"용어 통일: {', '.join(terms)}")

    banned = bible.get("banned") or []
    if banned:
        lines.append(f"금칙어: {', '.join(banned)}")

    length_target = bible.get("length_target", 0)
    if length_target:
        lines.append(f"목표 분량: {length_target}단어")

    return "\n".join(lines)


def _ordered_variants(glossary: dict) -> list[tuple[str, str]]:
    """(variant, canonical) 쌍을 길이 내림차순으로 정렬해 반환한다.

    긴 변형부터 치환해 부분 겹침을 방지한다. 동일 길이는 사전순으로 정렬해
    결정성을 보장한다.
    """
    pairs: list[tuple[str, str]] = []
    for canonical in glossary:
        for variant in glossary[canonical]:
            if variant:
                pairs.append((variant, canonical))
    pairs.sort(key=lambda p: (-len(p[0]), p[0]))
    return pairs


def apply_glossary(text: str, glossary: dict | None) -> str:
    """각 변형을 정규 용어로 결정적으로 치환한다.

    긴 변형부터 치환해 부분 겹침을 방지한다. glossary 가 비어 있으면 입력을
    그대로 반환한다.
    """
    if not glossary:
        return text

    for variant, canonical in _ordered_variants(glossary):
        text = text.replace(variant, canonical)
    return text


def glossary_violations(text: str, glossary: dict | None) -> list[dict]:
    """텍스트에 남아 있는 변형마다 {"found","canonical"} 를 반환한다 (QA 용)."""
    if not glossary:
        return []

    out: list[dict] = []
    for variant, canonical in _ordered_variants(glossary):
        # 변형이 정규 용어와 동일하면 위반이 아니다.
        if variant == canonical:
            continue
        if variant in text:
            out.append({"found": variant, "canonical": canonical})
    return out
