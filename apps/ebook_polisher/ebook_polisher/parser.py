"""원고 파서 모듈.

TextParser 는 models.Parser 프로토콜을 구현한다(.txt / .md 지원).
ID 생성 규칙은 다운스트림(청커)이 의존하므로 절대 어긋나면 안 된다:
  - page_id  = "p" + 6자리 0패딩 페이지 번호 (1부터). 예: "p000001"
  - block_id = "b" + 6자리 0패딩 전역 카운터 (1부터). 예: "b000001"
  - order_index = 책 전체 기준 0부터 순차 증가하는 int
"""
from __future__ import annotations

from ebook_polisher.models import Block, Page, sha256_text
from ebook_polisher.normalizer import normalize_text


def _make_page_id(page_number: int) -> str:
    """페이지 번호(1부터)를 'pNNNNNN' 형식으로."""
    return f"p{page_number:06d}"


def _make_block_id(counter: int) -> str:
    """전역 블록 카운터(1부터)를 'bNNNNNN' 형식으로."""
    return f"b{counter:06d}"


def _split_pages(raw: str) -> list[str]:
    """원문을 페이지 텍스트 목록으로 나눈다.

    규칙:
      - 폼피드('\\f')가 있으면 그것으로 분할.
      - 없으면 최상위 H1('# ')이 새 페이지를 시작. (그 외엔 단일 페이지)
      - 항상 최소 1페이지.
    """
    if "\f" in raw:
        parts = raw.split("\f")
        pages = [p for p in parts]
        return pages if pages else [""]

    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    pages: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("# "):
            # 새 H1을 만나면 이전 페이지를 닫고 새 페이지 시작.
            if current:
                pages.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        pages.append("\n".join(current))

    return pages if pages else [""]


def _classify_block(block_lines: list[str]) -> str:
    """블록(빈 줄로 구분된 묶음)의 타입을 판정한다."""
    first = block_lines[0].lstrip()

    # 펜스 코드 또는 디스플레이 수식 -> formula
    if first.startswith("```") or first.startswith("~~~") or first.startswith("$$"):
        return "formula"

    # 제목: #, ##, ### (뒤에 공백 또는 끝)
    stripped = first
    if stripped.startswith("#"):
        hashes = len(stripped) - len(stripped.lstrip("#"))
        if 1 <= hashes <= 3:
            rest = stripped[hashes:]
            if rest == "" or rest.startswith(" "):
                return "title"

    # 인용: 모든(첫) 줄이 '>' 로 시작
    if first.startswith(">"):
        return "quote"

    # 표: 줄이 '|' 로 시작
    if first.startswith("|"):
        return "table"

    return "paragraph"


def _split_blocks(page_text: str) -> list[tuple[str, str]]:
    """페이지 텍스트를 (block_type, normalized_text) 목록으로 분할한다.

    빈 줄(blank line)을 기준으로 문단 블록을 나눈다. 빈 블록은 건너뛴다.
    """
    text = page_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    blocks: list[tuple[str, str]] = []
    current: list[str] = []

    def flush() -> None:
        if not current:
            return
        block_type = _classify_block(current)
        normalized = normalize_text("\n".join(current))
        if normalized.strip():
            blocks.append((block_type, normalized))

    for line in lines:
        if line.strip() == "":
            flush()
            current = []
        else:
            current.append(line)
    flush()

    return blocks


class TextParser:
    """.txt / .md 원고를 Page 목록으로 파싱한다(Parser 프로토콜 구현)."""

    def parse(self, source_path: str) -> list[Page]:
        with open(source_path, "r", encoding="utf-8") as f:
            raw = f.read()

        page_texts = _split_pages(raw)

        pages: list[Page] = []
        global_block_counter = 0
        global_order_index = 0

        for page_idx, page_text in enumerate(page_texts, start=1):
            page_id = _make_page_id(page_idx)
            block_specs = _split_blocks(page_text)

            blocks: list[Block] = []
            for block_type, block_text in block_specs:
                global_block_counter += 1
                block = Block(
                    block_id=_make_block_id(global_block_counter),
                    page_id=page_id,
                    order_index=global_order_index,
                    block_type=block_type,
                    text=block_text,
                    source_hash=sha256_text(block_text),
                )
                global_order_index += 1
                blocks.append(block)

            raw_text = page_text
            page = Page(
                page_id=page_id,
                page_number=page_idx,
                blocks=blocks,
                raw_text=raw_text,
                normalized_text=normalize_text(page_text),
                source_hash=sha256_text(raw_text),
            )
            pages.append(page)

        return pages


def parse_file(path: str) -> list[Page]:
    """편의 함수: 기본 TextParser 로 파일을 파싱한다."""
    return TextParser().parse(path)
