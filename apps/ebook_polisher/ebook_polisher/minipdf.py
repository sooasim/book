"""의존성 없는(stdlib-only) 최소 PDF 작성기.

reportlab / weasyprint 가 설치되지 않은 환경에서도 PDF 내보내기가 항상
오프라인으로 동작하도록 한다. 출력은 구조적으로 유효하고 뷰어에서 열 수 있는
PDF 이며, 본문 폰트는 base-14 표준 폰트인 Helvetica, 제목은 Helvetica-Bold
를 WinAnsi 인코딩으로 사용한다.

한계
----
base-14 표준 폰트는 라틴(WinAnsi, codepoint <= 0xFF) 글리프만 표현할 수 있다.
한국어를 비롯한 CJK / 비라틴 문자(codepoint > 0xFF)는 표현할 수 없으므로
'?' 로 치환된다. 한국어 등 비라틴 텍스트가 중요한 경우에는 EPUB 내보내기를
권장하며, reportlab 또는 weasyprint 를 설치하면 임베디드 폰트로 더 높은
품질의 PDF 를 얻을 수 있다.

이 모듈은 입력으로 엔진의 관례인 ``blocks: list[tuple[str, str]]`` =
(block_type, text) 를 받는다. 'title' 블록은 큰 굵은 글씨의 제목으로,
그 외 블록은 본문 문단으로 배치된다.
"""
from __future__ import annotations

from pathlib import Path

# 레이아웃 상수 (PDF 포인트 = 1/72 인치).
_MARGIN = 56.0           # 약 0.78인치 좌우상하 여백
_BODY_SIZE = 11.0
_TITLE_SIZE = 18.0
_BODY_LEADING = 15.0     # 본문 줄간격
_TITLE_LEADING = 24.0    # 제목 줄간격
_PARA_GAP = 6.0          # 문단 사이 추가 간격

# Helvetica 의 폭은 글자마다 다르지만, 줄바꿈을 위해 평균 폭으로 근사한다.
# Helvetica 평균 advance 는 대략 0.5 em.
_AVG_WIDTH_RATIO = 0.5


def escape_pdf_text(s: str) -> str:
    """PDF 텍스트 문자열 리터럴용으로 문자열을 이스케이프한다.

    - 백슬래시, 여는/닫는 괄호를 이스케이프한다.
    - WinAnsi(latin-1, codepoint <= 0xFF) 범위를 벗어나는 문자(codepoint > 255)는
      base-14 폰트로 표현할 수 없으므로 '?' 로 치환한다.
    """
    out = []
    for ch in s:
        cp = ord(ch)
        if cp > 0xFF:
            # base-14 / WinAnsi 로 표현 불가 → 물음표.
            out.append("?")
            continue
        if ch == "\\":
            out.append("\\\\")
        elif ch == "(":
            out.append("\\(")
        elif ch == ")":
            out.append("\\)")
        else:
            out.append(ch)
    return "".join(out)


def _block_text(block_type: str, text: str) -> str:
    """표시용 텍스트 정리. 제목 블록의 마크다운 '#' 접두를 제거한다."""
    if block_type == "title":
        return text.lstrip("#").strip()
    return text.strip()


def _wrap_line(line: str, font_size: float, max_width: float) -> list[str]:
    """단어 단위로 긴 줄을 근사 글자 폭에 맞춰 줄바꿈한다.

    Helvetica 의 정확한 글자 폭 테이블을 쓰지 않고 평균 advance 로 근사한다.
    매우 긴 단어(공백 없는 토큰)는 문자 단위로 강제 분할한다.
    """
    char_width = font_size * _AVG_WIDTH_RATIO
    if char_width <= 0:
        return [line]
    max_chars = max(1, int(max_width / char_width))

    words = line.split(" ")
    lines: list[str] = []
    cur = ""
    for word in words:
        # 단어 자체가 한 줄보다 길면 문자 단위로 분할.
        while len(word) > max_chars:
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(word[:max_chars])
            word = word[max_chars:]
        candidate = word if not cur else cur + " " + word
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur or not lines:
        lines.append(cur)
    return lines


def _layout(blocks, title):
    """blocks → 페이지 목록. 각 페이지는 (x, y, font_size, bold, text_line) 의 목록.

    위에서 아래로 배치하고, 세로 공간이 부족하면 새 페이지를 시작한다.
    """
    width, height = _PAGE_SIZE
    text_width = width - 2 * _MARGIN
    top = height - _MARGIN
    bottom = _MARGIN

    pages: list[list[tuple]] = []
    current: list[tuple] = []
    y = top

    def new_page():
        nonlocal current, y
        if current:
            pages.append(current)
        current = []
        y = top

    def emit_paragraph(text, font_size, leading, bold):
        nonlocal y
        for raw_line in text.split("\n"):
            wrapped = _wrap_line(raw_line, font_size, text_width) or [""]
            for wl in wrapped:
                if y - leading < bottom:
                    new_page()
                y -= leading
                current.append((_MARGIN, y, font_size, bold, wl))
        # 문단 사이 간격.
        y -= _PARA_GAP

    if title:
        emit_paragraph(title, _TITLE_SIZE, _TITLE_LEADING, True)

    for btype, text in blocks:
        t = _block_text(btype, text)
        if not t:
            continue
        if btype == "title":
            emit_paragraph(t, _TITLE_SIZE, _TITLE_LEADING, True)
        else:
            emit_paragraph(t, _BODY_SIZE, _BODY_LEADING, False)

    if current:
        pages.append(current)
    if not pages:
        pages.append([])  # 최소 1페이지 보장.
    return pages


def _content_stream(page_lines) -> bytes:
    """한 페이지의 텍스트 라인 목록을 PDF content stream 바이트로 변환한다."""
    parts = ["BT"]
    cur_font = None
    cur_size = None
    for x, y, size, bold, text in page_lines:
        font = "F2" if bold else "F1"
        if font != cur_font or size != cur_size:
            parts.append(f"/{font} {size:.2f} Tf")
            cur_font = font
            cur_size = size
        esc = escape_pdf_text(text)
        # 절대 좌표로 각 라인을 배치 (Td 누적 대신 Tm 사용).
        parts.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm")
        parts.append(f"({esc}) Tj")
    parts.append("ET")
    body = "\n".join(parts)
    return body.encode("latin-1", errors="replace")


# 모듈 전역으로 현재 페이지 크기를 전달 (pdf_bytes 에서 설정).
_PAGE_SIZE = (595, 842)


def pdf_bytes(blocks, title: str = "", page_size=(595, 842)) -> bytes:
    """blocks 로부터 유효한 PDF 바이트를 생성해 반환한다.

    write_pdf 에서 사용된다. 결정적(deterministic)이며, 날짜 등 비결정적
    메타데이터는 포함하지 않는다.
    """
    global _PAGE_SIZE
    _PAGE_SIZE = (float(page_size[0]), float(page_size[1]))
    width, height = _PAGE_SIZE

    pages = _layout(blocks, title)
    n_pages = len(pages)

    # 객체 번호 배치:
    #   1: Catalog
    #   2: Pages
    #   3: Font F1 (Helvetica)
    #   4: Font F2 (Helvetica-Bold)
    #   5..(5+n-1): Page 객체
    #   다음: 각 Page 의 Contents stream
    first_page_obj = 5
    first_content_obj = first_page_obj + n_pages
    page_obj_ids = [first_page_obj + i for i in range(n_pages)]
    content_obj_ids = [first_content_obj + i for i in range(n_pages)]
    total_objs = 4 + 2 * n_pages

    objects: dict[int, bytes] = {}

    # 1: Catalog
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"

    # 2: Pages
    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objects[2] = (
        f"<< /Type /Pages /Count {n_pages} /Kids [{kids}] >>"
    ).encode("latin-1")

    # 3: Font Helvetica (F1)
    objects[3] = (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>"
    )
    # 4: Font Helvetica-Bold (F2)
    objects[4] = (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        b"/Encoding /WinAnsiEncoding >>"
    )

    # Page 객체들.
    for i, page in enumerate(pages):
        pid = page_obj_ids[i]
        cid = content_obj_ids[i]
        page_dict = (
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {width:.2f} {height:.2f}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
            f"/Contents {cid} 0 R >>"
        ).encode("latin-1")
        objects[pid] = page_dict

    # Contents stream 객체들.
    for i, page in enumerate(pages):
        cid = content_obj_ids[i]
        stream = _content_stream(page)
        obj = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream"
        )
        objects[cid] = obj

    # 직렬화: 헤더 + 객체들, 바이트 오프셋을 추적해 xref 구성.
    out = bytearray()
    out += b"%PDF-1.4\n"
    # 바이너리 표시 주석(일부 도구가 바이너리 파일로 인식하도록).
    out += b"%\xe2\xe3\xcf\xd3\n"

    offsets: dict[int, int] = {}
    for obj_id in range(1, total_objs + 1):
        offsets[obj_id] = len(out)
        out += f"{obj_id} 0 obj\n".encode("latin-1")
        out += objects[obj_id]
        out += b"\nendobj\n"

    # xref 테이블.
    xref_offset = len(out)
    size = total_objs + 1  # 객체 0 (free) 포함.
    out += b"xref\n"
    out += f"0 {size}\n".encode("latin-1")
    # 객체 0: free.
    out += b"0000000000 65535 f \n"
    for obj_id in range(1, total_objs + 1):
        out += f"{offsets[obj_id]:010d} 00000 n \n".encode("latin-1")

    # trailer.
    out += b"trailer\n"
    out += f"<< /Size {size} /Root 1 0 R >>\n".encode("latin-1")
    out += b"startxref\n"
    out += f"{xref_offset}\n".encode("latin-1")
    out += b"%%EOF\n"

    return bytes(out)


def write_pdf(blocks, path, title: str = "", page_size=(595, 842)) -> str:
    """blocks 를 유효한 PDF 파일로 쓴다. 작성한 경로를 반환한다.

    기본 page_size 는 A4 (595 x 842 포인트). 부모 디렉터리는 자동 생성한다.
    """
    data = pdf_bytes(blocks, title=title, page_size=page_size)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return str(p)
