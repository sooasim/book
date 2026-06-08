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
    formats = {"md": True, "docx": False, "epub": False}
    try:
        import docx  # noqa: F401
        formats["docx"] = True
    except Exception:
        pass
    try:
        import ebooklib  # noqa: F401
        formats["epub"] = True
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
