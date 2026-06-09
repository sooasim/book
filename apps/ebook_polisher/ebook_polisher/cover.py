"""결정적(deterministic) 전자책 표지 생성기 — 표준 라이브러리만 사용.

오프라인에서 동작해야 하므로 외부/네트워크/이미지 라이브러리에 의존하지 않는다.
표지는 SVG 로 그리며, 동일 입력은 항상 동일한 문자열을 만든다.

- 배경색: sha256(title) 에서 유도(결정적).
- 제목: 글자 수 기준 그리디 줄바꿈(CJK 친화), 최대 줄 수 초과 시 말줄임.
- 부제/저자: 옵션. 모든 사용자 텍스트는 XML 이스케이프.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

# 표지 레이아웃 상수.
_WRAP_CHARS = 11           # 한 줄당 대략적인 글자 수.
_MAX_TITLE_LINES = 5       # 제목 최대 줄 수.
_SUB_WRAP_CHARS = 22       # 부제 한 줄당 글자 수.
_MAX_SUB_LINES = 2         # 부제 최대 줄 수.


def _xml_escape(text: str) -> str:
    """XML 텍스트/속성에서 위험한 5개 문자를 모두 이스케이프한다."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _hash_bytes(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


def _bg_color(title: str) -> str:
    """sha256(title) 에서 적당히 어둡고 채도 있는 배경색을 유도한다."""
    h = _hash_bytes(title)
    # 0..255 바이트를 64..200 범위로 눌러 너무 밝거나 어둡지 않게.
    r = 64 + (h[0] % 137)
    g = 64 + (h[1] % 137)
    b = 64 + (h[2] % 137)
    return f"#{r:02x}{g:02x}{b:02x}"


def _darker(color: str, factor: float = 0.55) -> str:
    """'#rrggbb' 를 비율만큼 어둡게 만든다."""
    r = int(int(color[1:3], 16) * factor)
    g = int(int(color[3:5], 16) * factor)
    b = int(int(color[5:7], 16) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _wrap(text: str, width: int, max_lines: int) -> list[str]:
    """글자 수 기준 그리디 줄바꿈. 단어 경계가 있으면 활용하고,
    없으면(CJK 등) 글자 단위로 자른다. 줄 수 초과 시 마지막 줄에 말줄임.
    """
    text = text.strip()
    if not text:
        return []

    lines: list[str] = []
    line = ""
    for token, sep in _tokens(text):
        candidate = line + sep + token if line else token
        if len(candidate) <= width:
            line = candidate
            continue
        # 토큰 자체가 너무 길면 글자 단위로 강제 분할.
        if len(token) > width:
            if line:
                lines.append(line)
                line = ""
            line = _push_long_token(token, width, lines, line)
        else:
            if line:
                lines.append(line)
            line = token
    if line:
        lines.append(line)

    return _apply_max_lines(lines, width, max_lines)


def _tokens(text: str):
    """텍스트를 (토큰, 선행구분자) 로 분해한다.

    공백으로 단어를 나누되, 단어 사이는 공백 1개로 정규화한다.
    """
    for i, word in enumerate(text.split()):
        yield word, ("" if i == 0 else " ")


def _push_long_token(token: str, width: int, lines: list[str], line: str) -> str:
    """width 보다 긴 단일 토큰을 글자 단위로 잘라 lines 에 채운다.
    마지막(미완성) 줄을 반환한다.
    """
    cur = line
    for ch in token:
        if len(cur) + 1 > width:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    return cur


def _apply_max_lines(lines: list[str], width: int, max_lines: int) -> list[str]:
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    last = kept[-1]
    # 말줄임표(…) 자리를 확보.
    if len(last) >= width:
        last = last[: max(0, width - 1)]
    kept[-1] = last.rstrip() + "…"
    return kept


def _text_block(
    lines: list[str],
    *,
    cx: int,
    y: int,
    line_height: int,
    font_size: int,
    fill: str,
    weight: str,
) -> str:
    """가운데 정렬된 여러 줄 <text> 블록을 만든다(각 줄은 <tspan>)."""
    if not lines:
        return ""
    parts = [
        f'<text x="{cx}" y="{y}" text-anchor="middle" '
        f'font-family="Helvetica, Arial, sans-serif" '
        f'font-size="{font_size}" font-weight="{weight}" fill="{fill}">'
    ]
    for i, ln in enumerate(lines):
        dy = 0 if i == 0 else line_height
        parts.append(f'<tspan x="{cx}" dy="{dy}">{_xml_escape(ln)}</tspan>')
    parts.append("</text>")
    return "".join(parts)


def cover_svg(
    title: str,
    author: str = "",
    subtitle: str = "",
    width: int = 1600,
    height: int = 2560,
) -> str:
    """결정적인 전자책 표지 SVG 문서(문자열)를 반환한다."""
    title = title if title is not None else ""
    author = author if author is not None else ""
    subtitle = subtitle if subtitle is not None else ""

    bg = _bg_color(title)
    footer = _darker(bg)
    cx = width // 2

    # 폰트 크기는 표지 너비에 비례시켜 다양한 크기에서도 보기 좋게.
    title_fs = max(36, width // 13)
    sub_fs = max(20, width // 28)
    author_fs = max(20, width // 32)
    title_lh = int(title_fs * 1.18)
    sub_lh = int(sub_fs * 1.2)

    title_lines = _wrap(title, _WRAP_CHARS, _MAX_TITLE_LINES)
    sub_lines = _wrap(subtitle, _SUB_WRAP_CHARS, _MAX_SUB_LINES)

    footer_h = int(height * 0.12)
    footer_y = height - footer_h

    # 제목 블록을 표지 위쪽 1/3 지점 부근에서 시작.
    title_y = int(height * 0.30)
    out = [
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>',
        f'<rect x="0" y="{footer_y}" width="{width}" height="{footer_h}" fill="{footer}"/>',
    ]

    # 제목 위쪽에 가느다란 장식선(결정적, 사용자 입력 무관).
    rule_y = title_y - title_fs
    rule_w = width // 4
    out.append(
        f'<rect x="{cx - rule_w // 2}" y="{rule_y}" '
        f'width="{rule_w}" height="6" fill="#ffffff" fill-opacity="0.85"/>'
    )

    title_block = _text_block(
        title_lines,
        cx=cx,
        y=title_y,
        line_height=title_lh,
        font_size=title_fs,
        fill="#ffffff",
        weight="bold",
    )
    if title_block:
        out.append(title_block)

    if sub_lines:
        sub_y = title_y + len(title_lines) * title_lh + sub_fs
        out.append(
            _text_block(
                sub_lines,
                cx=cx,
                y=sub_y,
                line_height=sub_lh,
                font_size=sub_fs,
                fill="#ffffff",
                weight="normal",
            )
        )

    if author.strip():
        author_y = footer_y + footer_h // 2 + author_fs // 3
        out.append(
            f'<text x="{cx}" y="{author_y}" text-anchor="middle" '
            f'font-family="Helvetica, Arial, sans-serif" '
            f'font-size="{author_fs}" font-weight="normal" fill="#ffffff">'
            f"{_xml_escape(author.strip())}</text>"
        )

    out.append("</svg>")
    return "".join(out)


def write_cover_svg(
    path: str,
    title: str,
    author: str = "",
    subtitle: str = "",
) -> str:
    """표지 SVG 를 파일로 쓰고 경로를 반환한다(상위 디렉터리 자동 생성)."""
    svg = cover_svg(title, author=author, subtitle=subtitle)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(svg, encoding="utf-8")
    return str(p)


def svg_to_png(svg: str, path: str) -> str:
    """SVG 문자열을 PNG 로 변환(cairosvg 필요). 없으면 RuntimeError.

    테스트에서는 사용하지 않는 스켈레톤이다.
    """
    try:
        import cairosvg  # noqa: F401
    except Exception as exc:  # pragma: no cover - 의존성 없을 때
        raise RuntimeError(
            "PNG 변환에는 cairosvg 가 필요합니다: pip install cairosvg"
        ) from exc
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=path)
    return path
