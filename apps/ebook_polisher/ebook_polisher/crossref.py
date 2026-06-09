"""앵커 참조 검증 (Cross-reference / Anchor Validation — OCES 03 §3.3 "앵커 참조").

장형(long-form) 생성 도서는 흔히 "앞서 3장에서 다룬…" 또는 "제5장 참조"처럼
다른 장/절을 가리키는 표현을 만든다. 책의 실제 장 수가 N인데 N보다 큰 장(또는
1보다 작은 장)을 가리키면 끊어진 상호 참조(broken cross-reference)이다.

이 모듈은 본문에서 한국어 장/절 참조를 결정론적 정규식으로 찾아내고, 주어진
장 수(및 선택적으로 장당 절 수)에 비추어 위반을 보고한다.

정직 봉인 철학에 따라 텍스트를 고치지 않고 '리포트'만 한다.
순수·결정론 함수로 구성되며 표준 라이브러리(re)만 사용한다.
"""
from __future__ import annotations

import re

from ebook_polisher.models import Block

# --------------------------------------------------------------------------- 정규식
# 장: "제?\\s*(\\d+)\\s*장"  (예: "3장", "제3장", "제 3 장")
# 절: "제?\\s*(\\d+)\\s*절"
# "장"/"절" 접미사를 요구하므로 "2026년" 같은 연도 숫자는 매칭되지 않는다.
_CHAPTER_RE = re.compile(r"제?\s*(\d+)\s*장")
_SECTION_RE = re.compile(r"제?\s*(\d+)\s*절")


def find_references(text: str) -> list[dict]:
    """본문에서 한국어 장/절 참조를 찾아 출현 순서대로 반환한다.

    반환 항목: {"kind": "chapter"|"section", "num": int, "raw": matched_text}
    동일한 (kind, num) 쌍은 중복 제거하며 처음 등장한 raw를 보존한다.
    """
    if not text:
        return []

    matches: list[tuple[int, str, int, str]] = []  # (위치, kind, num, raw)
    # raw는 선행/후행 공백을 제거한다. 선행 \s*가 앞 공백까지 삼키더라도("  3장")
    # 의미 있는 토큰만 남기되, "제 3 장"의 내부 공백은 보존한다.
    for m in _CHAPTER_RE.finditer(text):
        matches.append((m.start(), "chapter", int(m.group(1)), m.group(0).strip()))
    for m in _SECTION_RE.finditer(text):
        matches.append((m.start(), "section", int(m.group(1)), m.group(0).strip()))

    # 출현(시작 위치) 순서로 정렬. 동일 위치면 안정적으로 chapter < section 순.
    matches.sort(key=lambda t: (t[0], 0 if t[1] == "chapter" else 1))

    seen: set[tuple[str, int]] = set()
    refs: list[dict] = []
    for _pos, kind, num, raw in matches:
        key = (kind, num)
        if key in seen:
            continue
        seen.add(key)
        refs.append({"kind": kind, "num": num, "raw": raw})
    return refs


def validate_references(
    blocks: list,
    n_chapters: int,
    n_sections_per_chapter: int | None = None,
) -> dict:
    """모든 블록 본문을 훑어 참조를 모으고 범위를 벗어난 참조를 위반으로 보고한다.

    위반 기준:
      - 장 참조 num < 1 또는 num > n_chapters
      - (n_sections_per_chapter 제공 시) 절 참조 num이 [1, n_sections_per_chapter] 밖

    total_refs는 블록별 중복 제거 후 참조 수의 합이다. find_references가
    (kind,num)을 블록 단위로 중복 제거하므로, 같은 블록에서 "3장"이 두 번
    나와도 1로 센다(서로 다른 블록의 같은 참조는 각각 센다).

    반환: {"ok", "total_refs", "violations":[{block_id,kind,num,raw}], "chapters"}
    """
    total_refs = 0
    violations: list[dict] = []
    for block in blocks or []:
        text = block.polished_text or block.text
        refs = find_references(text)
        total_refs += len(refs)
        for ref in refs:
            kind, num = ref["kind"], ref["num"]
            bad = False
            if kind == "chapter":
                if num < 1 or num > n_chapters:
                    bad = True
            elif kind == "section":
                if n_sections_per_chapter is not None and (
                    num < 1 or num > n_sections_per_chapter
                ):
                    bad = True
            if bad:
                violations.append(
                    {
                        "block_id": block.block_id,
                        "kind": kind,
                        "num": num,
                        "raw": ref["raw"],
                    }
                )

    return {
        "ok": len(violations) == 0,
        "total_refs": total_refs,
        "violations": violations,
        "chapters": n_chapters,
    }


def crossref_report(
    blocks: list,
    n_chapters: int,
    n_sections_per_chapter: int | None = None,
) -> dict:
    """validate_references 결과에 {"checked": True}를 더한 얇은 래퍼.

    n_chapters <= 0 이면 장 수를 모르므로 검증할 수 없다. 이 경우
    {"ok": True, "total_refs": 0, "violations": [], "checked": False}를 반환한다.
    """
    if n_chapters <= 0:
        return {
            "ok": True,
            "total_refs": 0,
            "violations": [],
            "checked": False,
        }
    result = validate_references(blocks, n_chapters, n_sections_per_chapter)
    result["checked"] = True
    return result
