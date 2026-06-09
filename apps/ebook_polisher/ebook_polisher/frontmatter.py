"""OCES 03 §6 LAYOUT — 프런트매터(앞부속) 생성 모듈.

엔진은 본문을 ``list[tuple[str, str]]`` = (block_type, text) 로 표현한다.
block_type ∈ {"title","paragraph","quote","footnote","table","formula","caption"}.

이 모듈은 내보내기(epub/pdf/html) 시점에 본문 앞에 붙일 '장식용' 블록만 만든다:
  - 표제지(title page)
  - 판권지(copyright)
  - 목차(TOC)

본문 커버리지(coverage)는 절대 바꾸지 않는다 — 어디까지나 export 전용 데코레이션이다.
모든 함수는 결정적(deterministic): 같은 입력 → 같은 출력. (연도 기본값만 UTC now에 의존)
표준 라이브러리(datetime)만 사용한다.
"""
from __future__ import annotations

from datetime import datetime, timezone

# 본문/프런트매터에 허용되는 블록 타입 (엔진 계약).
ALLOWED_BLOCK_TYPES = {
    "title",
    "paragraph",
    "quote",
    "footnote",
    "table",
    "formula",
    "caption",
}

# 제작 크레딧 라인 (판권지 하단).
STUDIO_CREDIT = "이 책은 OneClick eBook Studio로 제작되었습니다."


def _current_utc_year() -> int:
    """현재 UTC 연도. 연도 기본값에만 사용한다."""
    return datetime.now(timezone.utc).year


def title_page_blocks(
    title: str,
    author: str = "",
    subtitle: str = "",
) -> list[tuple[str, str]]:
    """표제지 블록을 만든다.

    [("title", title)]
      + [("paragraph", subtitle)]            (subtitle 있을 때만)
      + [("paragraph", f"지은이: {author}")]  (author 있을 때만)
    """
    blocks: list[tuple[str, str]] = [("title", title)]
    if subtitle:
        blocks.append(("paragraph", subtitle))
    if author:
        blocks.append(("paragraph", f"지은이: {author}"))
    return blocks


def copyright_blocks(
    title: str,
    author: str = "",
    year: int | None = None,
    publisher: str = "",
    isbn: str = "",
) -> list[tuple[str, str]]:
    """판권지 블록을 만든다.

    "판권" 제목 + 문단들:
      - ⓒ{year} {author}
      - 제목
      - 발행처(있을 때만)
      - ISBN(있을 때만)
      - 제작 크레딧 라인
    year 기본값은 현재 UTC 연도.
    """
    if year is None:
        year = _current_utc_year()

    blocks: list[tuple[str, str]] = [("title", "판권")]

    copyright_line = f"ⓒ{year} {author}".rstrip()
    blocks.append(("paragraph", copyright_line))
    blocks.append(("paragraph", title))
    if publisher:
        blocks.append(("paragraph", f"발행처: {publisher}"))
    if isbn:
        blocks.append(("paragraph", f"ISBN: {isbn}"))
    blocks.append(("paragraph", STUDIO_CREDIT))
    return blocks


def toc_blocks(chapters: list) -> list[tuple[str, str]]:
    """목차 블록을 만든다.

    chapters: 각 항목이 "title" 키(선택적 "idx")를 가진 dict 리스트.
    반환: [("title","목차")] + 챕터당 ("paragraph", f"{i+1}. {title}").
    챕터가 없으면 [] 를 반환한다(빈 목차 제목도 출력하지 않음).
    """
    if not chapters:
        return []
    blocks: list[tuple[str, str]] = [("title", "목차")]
    for i, ch in enumerate(chapters):
        title = ch.get("title", "") if isinstance(ch, dict) else str(ch)
        blocks.append(("paragraph", f"{i + 1}. {title}"))
    return blocks


def build_frontmatter(meta: dict, chapters: list) -> list[tuple[str, str]]:
    """표제지 + 판권지 + 목차를 합쳐 프런트매터 전체를 만든다.

    meta 키: title, author, subtitle?, year?, publisher?, isbn?.
    결정적(연도 기본값 제외).
    """
    title = meta.get("title", "")
    author = meta.get("author", "")
    subtitle = meta.get("subtitle", "")
    year = meta.get("year")
    publisher = meta.get("publisher", "")
    isbn = meta.get("isbn", "")

    blocks: list[tuple[str, str]] = []
    blocks += title_page_blocks(title, author=author, subtitle=subtitle)
    blocks += copyright_blocks(
        title,
        author=author,
        year=year,
        publisher=publisher,
        isbn=isbn,
    )
    blocks += toc_blocks(chapters)
    return blocks
