"""OneClick eBook Studio — 서비스 계층(순수 파이썬, 프레임워크 비의존).

oneclick-ebook-studio 의 더미 API(/api/projects, /api/compose/start)를
우리 실제 엔진(apps/ebook_polisher 파이프라인 + apps/ebook_publisher 제출팩)에 배선한다.

FastAPI 없이도 동작/테스트 가능하도록 비즈니스 로직을 여기에 둔다.
main.py(FastAPI)는 이 모듈을 호출만 한다.
"""
from __future__ import annotations

import sys
import tempfile
import uuid
from pathlib import Path

# 엔진 경로 부트스트랩: apps/ebook_polisher 를 import 경로에 추가
_APPS_DIR = Path(__file__).resolve().parents[1]          # .../apps
_ENGINE_DIR = _APPS_DIR / "ebook_polisher"
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from ebook_polisher.cli import build_pipeline  # noqa: E402  (경로 주입 후 import)
from ebook_polisher.compose import build_outline, compose_to_markdown  # noqa: E402
from ebook_polisher.llm_provider import get_provider  # noqa: E402

# 인메모리 프로젝트 저장소(다음 단계에서 DB 로 승격)
_PROJECTS: dict[str, dict] = {}


def reset_store() -> None:
    """테스트용 저장소 초기화."""
    _PROJECTS.clear()


def health() -> dict:
    return {"ok": True, "service": "oneclick-ebook-studio", "engine": "ebook_polisher v3"}


def create_project(title: str, topic: str = "", genre: str = "", author: str = "") -> dict:
    if not title or not title.strip():
        raise ValueError("title is required")
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    project = {
        "project_id": project_id,
        "title": title.strip(),
        "topic": topic.strip(),
        "genre": genre.strip(),
        "author": author.strip(),
        "status": "created",
        "result": None,
    }
    _PROJECTS[project_id] = project
    return project


def get_project(project_id: str) -> dict | None:
    return _PROJECTS.get(project_id)


def list_projects() -> list[dict]:
    return list(_PROJECTS.values())


def polish_text(text: str, title: str = "manuscript", mode: str = "rules",
                out_dir: str | None = None) -> dict:
    """원고 텍스트를 실제 엔진으로 윤문하고 coverage/QA/결과를 반환한다."""
    if mode not in ("rules", "agency"):
        raise ValueError("mode must be 'rules' or 'agency'")
    out_dir = out_dir or tempfile.mkdtemp(prefix="oces_")
    src = Path(tempfile.mkdtemp(prefix="oces_src_")) / "manuscript.md"
    src.write_text(text or "", encoding="utf-8")

    pipeline = build_pipeline(mode, ":memory:", out_dir)
    result = pipeline.run(str(src))

    polished_md = ""
    md_path = result.get("files", {}).get("md")
    if md_path and Path(md_path).exists():
        polished_md = Path(md_path).read_text(encoding="utf-8")

    return {
        "ok": result.get("ok", False),
        "reason": result.get("reason"),
        "coverage": result.get("coverage"),
        "qa": result.get("qa"),
        "pipeline": result.get("pipeline"),
        "polished_markdown": polished_md,
        "files": result.get("files", {}),
    }


def compose_book(title: str, topic: str, n_chapters: int = 6, length_target: int = 6000,
                 language: str = "ko", provider: str = "stub", mode: str = "rules") -> dict:
    """OCES 풀 파이프라인: 제목+주제 → (목차→집필) 생성 → 윤문 → EPUB/MD 출력.

    provider="stub" 은 오프라인 결정적 생성(키 불필요). "anthropic" 은 Claude 사용(키 필요).
    """
    if not title or not title.strip():
        raise ValueError("title is required")
    prov = get_provider(provider)
    outline = build_outline(title, topic, n_chapters=n_chapters,
                            length_target=length_target, language=language)
    manuscript = compose_to_markdown(title, topic, provider=prov, n_chapters=n_chapters,
                                     length_target=length_target, language=language)
    polish = polish_text(manuscript, title=title, mode=mode)
    return {
        "ok": polish["ok"],
        "title": title,
        "topic": topic,
        "outline": [
            {"idx": c.idx, "title": c.title, "brief": c.brief, "target_words": c.target_words}
            for c in outline.chapters
        ],
        "manuscript_markdown": manuscript,
        "polished_markdown": polish["polished_markdown"],
        "coverage": polish["coverage"],
        "qa": polish["qa"],
        "files": polish["files"],          # md/epub/html 산출물 경로
        "pipeline": polish["pipeline"],
    }


def compose_start(project_id: str, manuscript: str = "", mode: str = "rules") -> dict:
    """프로젝트 오케스트레이션 시작: 윤문 → (다음 단계) 변환/출판.

    현재 단계: 원고가 주어지면 실제 윤문 파이프라인을 실행하고 결과를 프로젝트에 저장.
    """
    project = _PROJECTS.get(project_id)
    if project is None:
        raise KeyError(f"unknown project_id: {project_id}")

    if manuscript.strip():
        # 원고가 주어지면 윤문만
        project["status"] = "polishing"
        result = polish_text(manuscript, title=project["title"], mode=mode)
    elif project.get("topic"):
        # 원고가 없고 주제가 있으면 OCES 생성→윤문 풀 파이프라인
        project["status"] = "composing"
        result = compose_book(project["title"], project["topic"], mode=mode)
    else:
        project["status"] = "started"
        return {"project_id": project_id, "status": "started", "note": "원고/주제가 없어 대기"}

    project["result"] = result
    project["status"] = "ready" if result["ok"] else "blocked"
    return {
        "project_id": project_id,
        "status": project["status"],
        "ok": result["ok"],
        "coverage_ok": (result.get("coverage") or {}).get("ok"),
        "qa_ok": (result.get("qa") or {}).get("ok"),
        "result": result,
    }
