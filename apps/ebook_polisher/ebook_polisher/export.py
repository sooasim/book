"""내보내기 유틸 — Markdown(코어) + DOCX/EPUB(선택, 의존성 있으면).

코어(E1)는 Markdown 만 보장한다. DOCX/EPUB 는 해당 라이브러리가 설치된 경우에만 동작하며,
없으면 명확한 안내와 함께 건너뛴다(파이프라인을 깨지 않는다).
"""
from __future__ import annotations

from pathlib import Path


def write_markdown(markdown: str, path: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(markdown, encoding="utf-8")
    return str(p)


def available_formats() -> dict:
    # md 와 epub 은 표준 라이브러리만으로 항상 가능하다.
    formats = {"md": True, "docx": False, "epub": True, "pdf": False}
    try:
        import docx  # noqa: F401
        formats["docx"] = True
    except Exception:
        pass
    # pdf 는 reportlab 또는 weasyprint 중 하나라도 있으면 가능.
    for mod in ("reportlab", "weasyprint"):
        try:
            __import__(mod)
            formats["pdf"] = True
            break
        except Exception:
            pass
    return formats


def to_docx(blocks_markdown: str, path: str) -> str:
    """문단 단위 DOCX. python-docx 필요."""
    try:
        from docx import Document
    except Exception as exc:  # pragma: no cover - 의존성 없을 때
        raise RuntimeError("python-docx 가 필요합니다: pip install python-docx") from exc
    doc = Document()
    for para in blocks_markdown.split("\n\n"):
        text = para.strip()
        if not text:
            continue
        if text.startswith("#"):
            level = len(text) - len(text.lstrip("#"))
            doc.add_heading(text.lstrip("# ").strip(), level=min(max(level, 1), 4))
        else:
            doc.add_paragraph(text)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


def _block_text(block_type: str, text: str) -> str:
    """제목 블록의 마크다운 '#' 제거 등 표시용 텍스트 정리."""
    if block_type == "title":
        return text.lstrip("#").strip()
    return text.strip()


def blocks_to_docx(blocks: list[tuple[str, str]], path: str, title: str = "") -> str:
    """[(block_type, text)] 목록으로 DOCX 작성.

    'title' 블록은 heading 으로, 나머지는 일반 문단으로 변환한다.
    python-docx 가 필요하며 없으면 RuntimeError.
    """
    try:
        from docx import Document
    except Exception as exc:  # pragma: no cover - 의존성 없을 때
        raise RuntimeError("python-docx 가 필요합니다: pip install python-docx") from exc
    doc = Document()
    if title:
        doc.add_heading(title, level=0)
    for btype, text in blocks:
        t = _block_text(btype, text)
        if not t:
            continue
        if btype == "title":
            doc.add_heading(t, level=1)
        else:
            doc.add_paragraph(t)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


def blocks_to_pdf(blocks: list[tuple[str, str]], path: str, title: str = "") -> str:
    """[(block_type, text)] 목록으로 PDF 작성 (reportlab 사용).

    'title' 블록은 Heading 스타일, 나머지는 BodyText 스타일로 변환한다.
    reportlab 이 없으면 RuntimeError.
    """
    try:
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except Exception as exc:  # pragma: no cover - 의존성 없을 때
        raise RuntimeError("reportlab 이 필요합니다: pip install reportlab") from exc

    def _xesc(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    story = []
    if title:
        story.append(Paragraph(_xesc(title), styles["Title"]))
        story.append(Spacer(1, 12))
    for btype, text in blocks:
        t = _block_text(btype, text)
        if not t:
            continue
        style = styles["Heading1"] if btype == "title" else styles["BodyText"]
        # 문단 내 줄바꿈은 <br/> 로 보존.
        safe = "<br/>".join(_xesc(line) for line in t.split("\n"))
        story.append(Paragraph(safe, style))
        story.append(Spacer(1, 6))
    doc = SimpleDocTemplate(str(path))
    doc.build(story)
    return path
