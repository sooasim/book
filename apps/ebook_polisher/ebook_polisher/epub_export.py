"""EPUB3 출력기 (표준 라이브러리만 사용).

EPUB 은 본질적으로 zip 컨테이너이므로 ebooklib 없이도 유효한 EPUB3 를 만들 수 있다.
규칙(EPUB3/OCF):
  - 'mimetype' 엔트리는 압축하지 않고(STORED) 가장 먼저 넣는다.
  - META-INF/container.xml 가 OPF 위치를 가리킨다.
  - content.opf(manifest/spine) + nav.xhtml(목차) + 챕터 XHTML.

본문은 'title' 블록을 기준으로 챕터를 나눈다(제목이 없으면 단일 챕터).
"""
from __future__ import annotations

import html
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

XHTML_HEAD = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<!DOCTYPE html>\n'
    '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}" lang="{lang}">\n'
    "<head><meta charset=\"utf-8\"/><title>{title}</title></head>\n<body>\n"
)
XHTML_TAIL = "</body>\n</html>\n"


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def _block_to_xhtml(block_type: str, text: str) -> str:
    """블록을 XHTML 조각으로 변환."""
    t = _esc(text.lstrip("#").strip()) if block_type == "title" else _esc(text)
    if block_type == "title":
        return f"<h2>{t}</h2>"
    if block_type == "quote":
        return f"<blockquote><p>{t}</p></blockquote>"
    if block_type in ("formula", "table"):
        return f"<pre>{t}</pre>"
    if block_type == "caption":
        return f"<p class=\"caption\"><em>{t}</em></p>"
    # paragraph: 줄바꿈 보존
    paras = [p for p in t.split("\n") if p.strip()]
    return "\n".join(f"<p>{p}</p>" for p in paras) or "<p></p>"


def _chapterize(blocks: list[tuple[str, str]]) -> list[dict]:
    """[(block_type, text)] → 챕터 목록. 'title' 블록마다 새 챕터 시작."""
    chapters: list[dict] = []
    current: dict | None = None
    for btype, text in blocks:
        if btype == "title" or current is None:
            title = text.lstrip("#").strip() if btype == "title" else "본문"
            current = {"title": title or "본문", "items": []}
            chapters.append(current)
        current["items"].append((btype, text))
    if not chapters:
        chapters = [{"title": "본문", "items": []}]
    return chapters


def write_epub(
    blocks: list[tuple[str, str]],
    path: str,
    title: str = "무제",
    author: str = "",
    language: str = "ko",
    identifier: str | None = None,
) -> str:
    """블록 목록으로 유효한 EPUB3 파일을 작성하고 경로를 반환한다."""
    identifier = identifier or f"urn:uuid:{uuid.uuid4()}"
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    chapters = _chapterize(blocks)

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 챕터 XHTML 생성
    chapter_files = []
    for i, chap in enumerate(chapters, 1):
        fname = f"text/chapter_{i:04d}.xhtml"
        body = "\n".join(_block_to_xhtml(bt, tx) for bt, tx in chap["items"]) or "<p></p>"
        content = XHTML_HEAD.format(lang=language, title=_esc(chap["title"])) + body + "\n" + XHTML_TAIL
        chapter_files.append({"id": f"chap{i:04d}", "href": fname,
                              "title": chap["title"], "content": content})

    # nav.xhtml (목차)
    nav_items = "\n".join(
        f'      <li><a href="{c["href"]}">{_esc(c["title"])}</a></li>' for c in chapter_files
    )
    nav = (
        XHTML_HEAD.format(lang=language, title="목차")
        + '<nav epub:type="toc" id="toc" xmlns:epub="http://www.idpf.org/2007/ops">\n'
        + "  <h1>목차</h1>\n  <ol>\n" + nav_items + "\n  </ol>\n</nav>\n"
        + XHTML_TAIL
    )

    # content.opf
    manifest = ['    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>']
    spine = []
    for c in chapter_files:
        manifest.append(
            f'    <item id="{c["id"]}" href="{c["href"]}" media-type="application/xhtml+xml"/>'
        )
        spine.append(f'    <itemref idref="{c["id"]}"/>')
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">\n'
        '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'    <dc:identifier id="bookid">{_esc(identifier)}</dc:identifier>\n'
        f'    <dc:title>{_esc(title)}</dc:title>\n'
        f'    <dc:language>{_esc(language)}</dc:language>\n'
        + (f'    <dc:creator>{_esc(author)}</dc:creator>\n' if author else "")
        + f'    <meta property="dcterms:modified">{modified}</meta>\n'
        '  </metadata>\n'
        '  <manifest>\n' + "\n".join(manifest) + "\n  </manifest>\n"
        '  <spine>\n' + "\n".join(spine) + "\n  </spine>\n"
        '</package>\n'
    )

    container = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        '  <rootfiles>\n'
        '    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
        '  </rootfiles>\n</container>\n'
    )

    with zipfile.ZipFile(out, "w") as zf:
        # mimetype 은 반드시 첫 엔트리·무압축(STORED)
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
        for c in chapter_files:
            zf.writestr(f"OEBPS/{c['href']}", c["content"], compress_type=zipfile.ZIP_DEFLATED)
    return str(out)


def write_html(blocks: list[tuple[str, str]], path: str, title: str = "무제",
               language: str = "ko") -> str:
    """단일 HTML 파일 출력(미리보기용)."""
    body = "\n".join(_block_to_xhtml(bt, tx) for bt, tx in blocks)
    doc = (
        f'<!DOCTYPE html>\n<html lang="{language}"><head><meta charset="utf-8"/>'
        f"<title>{_esc(title)}</title></head>\n<body>\n{body}\n</body></html>\n"
    )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc, encoding="utf-8")
    return str(p)
