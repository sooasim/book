#!/usr/bin/env python3
"""
윤문 체크리스트(600항목) Markdown -> JSON 변환기.

목적:
  resources/checklist/윤문교정_체크리스트_600.md 를 파싱해
  엔진이 소비할 수 있는 resources/checklist/checklist_600.json 을 생성한다.

설계 원칙:
  - 원본 Markdown이 "단일 진실원(single source of truth)"이다.
  - 이 스크립트는 재현 가능(idempotent)하다. 같은 입력 -> 같은 출력.
  - 각 항목에 part / category / text 와 함께 'suggested_method'(검사 라우팅 힌트)를
    휴리스틱으로 부여한다. 이는 권고일 뿐이며 추후 사람이 다듬을 수 있다.

suggested_method 값:
  rules        : 규칙엔진으로 (반)자동 점검 가능 (맞춤법/띄어쓰기/피동/부호 등)
  llm_review   : 문맥 판단이 필요해 LLM 보조 검토가 유효
  human_review : 사람의 최종 판단이 필요 (구조/논리/독자경험/사실검증)
  policy       : 정책·법무·권리·AI 고지 등 컴플라이언스 게이트
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# scripts -> ebook_publisher -> apps -> (repo root)
REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "resources" / "checklist" / "윤문교정_체크리스트_600.md"
DST = REPO_ROOT / "resources" / "checklist" / "checklist_600.json"

ITEM_RE = re.compile(r"^\s*(\d{1,3})\.\s+(.*\S)\s*$")
PART_RE = re.compile(r"^##\s+(.*\S)\s*$")
CATEGORY_RE = re.compile(r"^###\s+(.*\S)\s*$")

# 카테고리/키워드 -> 검사 라우팅 휴리스틱
RULES_KEYWORDS = (
    "띄어쓰기", "맞춤법", "오탈자", "오자", "탈자", "문장부호", "맞춤", "조사",
    "피동", "수동태", "사동", "부사", "접속어", "접속사", "종결어미", "어미",
    "번역투", "띄어", "들여쓰기", "공백", "따옴표", "괄호", "문장이 지나치게 길",
    "한 문장에", "비문", "호응", "수식어", "반복",
)
POLICY_KEYWORDS = (
    "저작권", "표절", "AI 생성 고지", "AI 생성", "고지", "윤리", "명예훼손",
    "프라이버시", "ISBN", "CIP", "판권", "라이선스", "약관", "법적", "법률",
    "권리", "인용 허락", "출처",
)
HUMAN_KEYWORDS = (
    "독자", "논리", "주장", "근거", "구조", "흐름", "사실", "검증", "일관",
    "몰입", "메시지", "완성", "기대",
)

# 카테고리명 기반 1차 라우팅
CATEGORY_METHOD = {
    "원고 전체 구조": "human_review",
    "문장 윤문": "rules",
    "AI 생성문 점검": "llm_review",
    "논리와 주장": "human_review",
    "수학·물리학·전문 이론서": "human_review",
    "소설·에세이·서사문": "llm_review",
    "자기개발·실용서·대중서": "llm_review",
    "사실 검증·출처·윤리": "policy",
    "교정·조판·출판 품질": "rules",
    "최종 독자 검수": "human_review",
}


def route(category: str, text: str) -> str:
    """카테고리 + 키워드로 검사 방법을 추정한다."""
    for kw in POLICY_KEYWORDS:
        if kw in text:
            return "policy"
    for kw in RULES_KEYWORDS:
        if kw in text:
            return "rules"
    if category in CATEGORY_METHOD:
        return CATEGORY_METHOD[category]
    for kw in HUMAN_KEYWORDS:
        if kw in text:
            return "human_review"
    return "human_review"


def clean(text: str) -> str:
    """항목 텍스트에서 굵게(**) 마크업과 군더더기 잡음을 제거한다."""
    text = text.replace("**", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse(md: str) -> list[dict]:
    part = ""
    category = ""
    items: list[dict] = []
    seen: set[int] = set()
    for line in md.splitlines():
        m = PART_RE.match(line)
        if m:
            part = m.group(1)
            category = ""
            continue
        m = CATEGORY_RE.match(line)
        if m:
            category = m.group(1)
            continue
        m = ITEM_RE.match(line)
        if not m:
            continue
        number = int(m.group(1))
        if number in seen:
            # 같은 번호가 본문에 다시 인용되는 경우 방지
            continue
        seen.add(number)
        text = clean(m.group(2))
        items.append(
            {
                "id": f"chk_{number:03d}",
                "number": number,
                "part": part,
                "category": category or "(2부 확장)",
                "text": text,
                "suggested_method": route(category, text),
                "mandatory": True,
            }
        )
    items.sort(key=lambda x: x["number"])
    return items


def main() -> int:
    if not SRC.exists():
        print(f"원본 없음: {SRC}", file=sys.stderr)
        return 1
    md = SRC.read_text(encoding="utf-8")
    items = parse(md)
    by_method: dict[str, int] = {}
    for it in items:
        by_method[it["suggested_method"]] = by_method.get(it["suggested_method"], 0) + 1
    doc = {
        "title": "출판용 AI 원고 윤문·교정·교열 체크리스트 600",
        "source": "resources/checklist/윤문교정_체크리스트_600.md",
        "version": "1.0",
        "total": len(items),
        "policy": "MANDATORY",  # 모든 윤문 실행에 반드시 적용
        "routing_summary": by_method,
        "items": items,
    }
    DST.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"생성: {DST}  (총 {len(items)}항목)")
    print(f"라우팅 요약: {by_method}")
    expected = 600
    if len(items) != expected:
        print(f"경고: 항목 수가 {expected}이 아닙니다 ({len(items)}).", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
