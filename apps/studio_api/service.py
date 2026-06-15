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
from ebook_polisher.compose import build_outline, write_book  # noqa: E402
from ebook_polisher.llm_provider import get_provider  # noqa: E402
from ebook_polisher.rag import build_store_from_sources, rag_context  # noqa: E402

import os  # noqa: E402

import jobs as jobs_mod  # noqa: E402  (studio_api/jobs.py)
import persistence as persistence_mod  # noqa: E402
import usage as usage_mod  # noqa: E402

# 프로젝트 인메모리 캐시 + SQLite 영속화(재시작 복구; PostgreSQL 승격 경로 동일 스키마)
_PROJECTS: dict[str, dict] = {}
_WORKSPACE = Path(tempfile.gettempdir()) / "oces_workspace"
JOBS = jobs_mod.JobStore()
_DB_PATH = os.environ.get("OCES_DB", ":memory:")
STORE = persistence_mod.Store(_DB_PATH)
_JOB_SPECS: dict[str, dict] = {}   # job_id -> {project_id, provider, mode}


def _load_from_store() -> None:
    """영속 저장소에서 프로젝트/잡 캐시를 복원(재시작 복구)."""
    for pid, proj in STORE.load_projects().items():
        _PROJECTS[pid] = proj
    JOBS.load(STORE.load_jobs())
    # 잡 변경을 SQLite 에 영속화(이벤트 포함)
    JOBS.set_persister(STORE.save_job)


def _persist_project(project: dict) -> None:
    project["updated_at"] = _now_iso()
    STORE.save_project(project)


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def reset_store() -> None:
    """테스트용 저장소 초기화."""
    _PROJECTS.clear()
    JOBS.reset()
    _JOB_SPECS.clear()
    STORE.delete_all()
    usage_mod.tracker.reset()


def _project_out_dir(project_id: str) -> Path:
    d = _WORKSPACE / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _assemble_markdown(title: str, chapters) -> str:
    parts = [f"# {title}", ""]
    for ch in chapters:
        parts.append(f"## {ch.title}")
        parts.append("")
        parts.append(ch.content_md.strip())
        parts.append("")
    return "\n".join(parts).strip() + "\n"


def health() -> dict:
    return {"ok": True, "service": "oneclick-ebook-studio", "engine": "ebook_polisher v3"}


def create_project(title: str, topic: str = "", genre: str = "", author: str = "",
                   audience: str = "", tone: str = "", language: str = "ko",
                   length_target: int = 6000, n_chapters: int = 6,
                   user_id: str = "public") -> dict:
    if not title or not title.strip():
        raise ValueError("title is required")
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    project = {
        "project_id": project_id,
        "user_id": user_id or "public",
        "title": title.strip(),
        "topic": topic.strip(),
        "genre": genre.strip(),
        "author": author.strip(),
        "audience": audience.strip(),
        "tone": tone.strip(),
        "language": language,
        "length_target": int(length_target),
        "n_chapters": int(n_chapters),
        "status": "created",
        "outline": [],          # [{idx,title,brief,target_words}]
        "chapters": [],         # [{idx,title,content_md,summary}]
        "sources": [],          # RAG 자료 [{id,text,uri}]
        "files": {},            # 산출물 경로
        "result": None,
    }
    _PROJECTS[project_id] = project
    _persist_project(project)
    return project


def get_project(project_id: str, user_id: str | None = None) -> dict | None:
    p = _PROJECTS.get(project_id)
    if p is None:
        return None
    if user_id is not None and p.get("user_id", "public") != user_id:
        return None  # 멀티테넌시: 소유자 스코프
    return p


def list_projects(user_id: str | None = None) -> list[dict]:
    items = list(_PROJECTS.values())
    if user_id is not None:
        items = [p for p in items if p.get("user_id", "public") == user_id]
    return items


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


def _generate(title: str, topic: str, n_chapters: int, length_target: int,
              language: str, provider: str, style_bible: str = "",
              sources: list[dict] | None = None):
    """목차 설계 + 본문 집필(+선택 RAG). Outline 객체와 원고 마크다운을 반환."""
    prov = get_provider(provider)
    outline = build_outline(title, topic, n_chapters=n_chapters,
                            length_target=length_target, language=language)
    # RAG: 자료가 있으면 챕터 브리프에 근거 컨텍스트를 주입(환각 억제, OCES 03 §3.4)
    if sources:
        store = build_store_from_sources(sources, provider=prov)
        for ch in outline.chapters:
            ctx = rag_context(ch.brief, store, k=3)
            if ctx:
                ch.brief = f"{ch.brief}\n{ctx}"
    write_book(outline, prov, style_bible=style_bible)
    manuscript = _assemble_markdown(title, outline.chapters)
    return outline, manuscript


def compose_book(title: str, topic: str, n_chapters: int = 6, length_target: int = 6000,
                 language: str = "ko", provider: str = "stub", mode: str = "rules",
                 out_dir: str | None = None, style_bible: str = "",
                 sources: list[dict] | None = None) -> dict:
    """OCES 풀 파이프라인: 제목+주제 → (목차→집필) 생성 → 윤문 → EPUB/MD 출력.

    provider="stub" 은 오프라인 결정적 생성(키 불필요). "anthropic" 은 Claude 사용(키 필요).
    """
    if not title or not title.strip():
        raise ValueError("title is required")
    outline, manuscript = _generate(title, topic, n_chapters, length_target,
                                    language, provider, style_bible, sources)
    polish = polish_text(manuscript, title=title, mode=mode, out_dir=out_dir)
    return {
        "ok": polish["ok"],
        "title": title,
        "topic": topic,
        "outline": [
            {"idx": c.idx, "title": c.title, "brief": c.brief, "target_words": c.target_words}
            for c in outline.chapters
        ],
        "chapters": [
            {"idx": c.idx, "title": c.title, "content_md": c.content_md, "summary": c.summary}
            for c in outline.chapters
        ],
        "manuscript_markdown": manuscript,
        "polished_markdown": polish["polished_markdown"],
        "coverage": polish["coverage"],
        "qa": polish["qa"],
        "files": polish["files"],          # md/epub/html 산출물 경로
        "pipeline": polish["pipeline"],
    }


# ---------------------------------------------------------------- 프로젝트 기반 오케스트레이션
def _store_compose_result(project: dict, result: dict) -> None:
    project["outline"] = result.get("outline", [])
    project["chapters"] = result.get("chapters", [])
    project["files"] = result.get("files", {})
    project["result"] = result
    project["status"] = "ready" if result["ok"] else "blocked"
    # 사용량/비용 집계(토큰 추정 = 원고 + 윤문본)
    tokens = usage_mod.estimate_tokens(result.get("manuscript_markdown", "")) + \
        usage_mod.estimate_tokens(result.get("polished_markdown", ""))
    usage_mod.tracker.record(project.get("user_id", "public"), tokens=tokens, books=1)
    project["cost_tokens"] = tokens
    _persist_project(project)


def compose_project(project_id: str, provider: str = "stub", mode: str = "rules") -> dict:
    """프로젝트의 제목/주제/옵션/자료로 풀 파이프라인 실행하고 결과를 프로젝트에 저장."""
    project = _PROJECTS.get(project_id)
    if project is None:
        raise KeyError(f"unknown project_id: {project_id}")
    if not project.get("topic"):
        raise ValueError("project has no topic to compose from")
    out_dir = str(_project_out_dir(project_id))
    # Style Bible: 프로젝트 옵션(독자/톤/말투/용어집)을 작가 프롬프트에 주입
    from ebook_polisher.style import build_style_bible, render_style_bible
    bible = build_style_bible(
        audience=project.get("audience", ""), tone=project.get("tone", ""),
        honorific=project.get("honorific", "plain"),
        glossary=project.get("glossary") or {}, length_target=project.get("length_target", 0))
    style_str = render_style_bible(bible)
    result = compose_book(
        project["title"], project["topic"], n_chapters=project["n_chapters"],
        length_target=project["length_target"], language=project["language"],
        provider=provider, mode=mode, out_dir=out_dir, sources=project.get("sources"),
        style_bible=style_str,
    )
    _store_compose_result(project, result)
    return result


def _compose_stages(project: dict, provider: str, mode: str):
    """compose 잡의 단계 목록(outline→write→edit→export)을 만든다."""
    project_id = project["project_id"]
    out_dir = str(_project_out_dir(project_id))

    def stage_outline(ctx):
        # 재개로 이미 ctx 에 산출이 있으면 재생성하지 않는다(중간 재개).
        if ctx.get("manuscript") and ctx.get("outline") is not None:
            return {"chapters": len(ctx["outline"].chapters), "resumed": True}
        outline, manuscript = _generate(
            project["title"], project["topic"], project["n_chapters"],
            project["length_target"], project["language"], provider,
            sources=project.get("sources"))
        ctx["outline"] = outline
        ctx["manuscript"] = manuscript
        # 중간 재개용 스냅샷 영속화(생성 단계는 가장 비싸므로 보존)
        project["_snapshot"] = {
            "manuscript": manuscript,
            "chapters": [{"idx": c.idx, "title": c.title, "brief": c.brief,
                          "target_words": c.target_words, "content_md": c.content_md,
                          "summary": c.summary} for c in outline.chapters],
        }
        _persist_project(project)
        return {"chapters": len(outline.chapters)}

    def stage_polish(ctx):
        polish = polish_text(ctx["manuscript"], title=project["title"], mode=mode, out_dir=out_dir)
        ctx["polish"] = polish
        return {"coverage_ok": (polish.get("coverage") or {}).get("ok")}

    def stage_export(ctx):
        outline = ctx["outline"]
        polish = ctx["polish"]
        result = {
            "ok": polish["ok"], "title": project["title"], "topic": project["topic"],
            "outline": [{"idx": c.idx, "title": c.title, "brief": c.brief,
                         "target_words": c.target_words} for c in outline.chapters],
            "chapters": [{"idx": c.idx, "title": c.title, "content_md": c.content_md,
                          "summary": c.summary} for c in outline.chapters],
            "manuscript_markdown": ctx["manuscript"],
            "polished_markdown": polish["polished_markdown"],
            "coverage": polish["coverage"], "qa": polish["qa"],
            "files": polish["files"], "pipeline": polish["pipeline"],
        }
        _store_compose_result(project, result)
        project.pop("_snapshot", None)  # 완료 시 재개 스냅샷 정리
        ctx["result"] = result
        return {"files": list(polish["files"].keys())}

    return [("outline", stage_outline), ("write", lambda ctx: None),
            ("edit", stage_polish), ("export", stage_export)]


def start_compose_job(project_id: str, provider: str = "stub", mode: str = "rules") -> dict:
    """비동기 잡으로 compose 단계를 실행하고 job_id 를 반환(SSE/폴링용 이벤트 기록)."""
    project = _PROJECTS.get(project_id)
    if project is None:
        raise KeyError(f"unknown project_id: {project_id}")
    job = JOBS.create(project_id, type="compose")
    job_id = job["id"]
    _JOB_SPECS[job_id] = {"project_id": project_id, "provider": provider, "mode": mode}
    stages = _compose_stages(project, provider, mode)
    project["status"] = "composing"
    jobs_mod.run_in_thread(JOBS, job_id, stages, context={})
    return {"job_id": job_id, "project_id": project_id, "status": "queued"}


def pause_job(job_id: str) -> dict:
    """HITL: 다음 단계 경계에서 멈추도록 일시정지 요청."""
    if JOBS.get(job_id) is None:
        raise KeyError(f"unknown job_id: {job_id}")
    return jobs_mod.request_pause(JOBS, job_id)


def resume_job(job_id: str) -> dict:
    """일시정지된 잡을 재개. outline 스냅샷이 있으면 생성 단계를 건너뛰고 중간부터 재개."""
    spec = _JOB_SPECS.get(job_id)
    job = JOBS.get(job_id)
    if spec is None or job is None:
        raise KeyError(f"unknown job_id: {job_id}")
    project = _PROJECTS.get(spec["project_id"])
    stages = _compose_stages(project, spec["provider"], spec["mode"])
    project["status"] = "composing"

    snap = project.get("_snapshot")
    if snap:  # 중간 재개: 원고/목차 복원 후 write 단계부터(생성 생략)
        from ebook_polisher.compose import Outline, OutlineChapter
        chaps = [OutlineChapter(idx=c["idx"], title=c["title"], brief=c["brief"],
                                target_words=c["target_words"], content_md=c["content_md"],
                                summary=c["summary"]) for c in snap["chapters"]]
        outline = Outline(title=project["title"], topic=project["topic"],
                          language=project["language"], chapters=chaps)
        ctx = {"outline": outline, "manuscript": snap["manuscript"]}
        start_index = 1
        resumed = "mid"
    else:  # 스냅샷 없으면 처음부터(결정적 재실행)
        ctx, start_index, resumed = {}, 0, "full"
    jobs_mod.run_in_thread(JOBS, job_id, stages, context=ctx, start_index=start_index)
    return {"job_id": job_id, "status": "resumed", "mode": resumed}


def get_job(job_id: str) -> dict | None:
    return JOBS.get(job_id)


def edit_chapter(project_id: str, idx: int, content_md: str, mode: str = "rules") -> dict:
    """챕터 본문을 사람이 직접 편집(자동저장) → 재조립·재윤문·재출력."""
    project = _PROJECTS.get(project_id)
    if project is None:
        raise KeyError(f"unknown project_id: {project_id}")
    chapters = project.get("chapters") or []
    target = next((c for c in chapters if c["idx"] == idx), None)
    if target is None:
        raise ValueError(f"chapter idx {idx} not found")
    target["content_md"] = content_md
    from types import SimpleNamespace
    chap_objs = [SimpleNamespace(title=c["title"], content_md=c["content_md"]) for c in chapters]
    manuscript = _assemble_markdown(project["title"], chap_objs)
    out_dir = str(_project_out_dir(project_id))
    polish = polish_text(manuscript, title=project["title"], mode=mode, out_dir=out_dir)
    project["files"] = polish["files"]
    project["chapters"] = chapters
    project["result"] = {**(project.get("result") or {}),
                         "polished_markdown": polish["polished_markdown"],
                         "coverage": polish["coverage"], "qa": polish["qa"],
                         "files": polish["files"], "chapters": chapters}
    _persist_project(project)
    return {"project_id": project_id, "idx": idx, "ok": polish["ok"],
            "coverage": polish["coverage"]}


def get_usage(user_id: str = "public") -> dict:
    return usage_mod.tracker.get(user_id)


def usage_dashboard() -> dict:
    return {"summary": usage_mod.tracker.summary(), "by_user": usage_mod.tracker.all()}


def regenerate_chapter(project_id: str, idx: int, provider: str = "stub",
                       mode: str = "rules") -> dict:
    """특정 챕터만 재집필하고 원고를 재조립·재윤문·재출력."""
    project = _PROJECTS.get(project_id)
    if project is None:
        raise KeyError(f"unknown project_id: {project_id}")
    chapters = project.get("chapters") or []
    target = next((c for c in chapters if c["idx"] == idx), None)
    if target is None:
        raise ValueError(f"chapter idx {idx} not found")

    prov = get_provider(provider)
    # 앞 챕터들의 요약을 carryover 로 사용
    from ebook_polisher.compose import OutlineChapter, Outline, write_book as _wb
    carry = " ".join(c.get("summary", "") for c in chapters if c["idx"] < idx)
    ch_obj = OutlineChapter(idx=idx, title=target["title"],
                            brief=target.get("title", ""), target_words=300)
    one = Outline(title=project["title"], topic=project["topic"],
                  language=project["language"], chapters=[ch_obj])
    # carryover 주입: 임시로 running summary 를 흉내내기 위해 brief 앞에 표시
    ch_obj.summary = carry
    _wb(one, prov)
    target["content_md"] = ch_obj.content_md
    target["summary"] = ch_obj.summary

    # 재조립 → 재윤문 → 재출력
    from types import SimpleNamespace
    chap_objs = [SimpleNamespace(title=c["title"], content_md=c["content_md"]) for c in chapters]
    manuscript = _assemble_markdown(project["title"], chap_objs)
    out_dir = str(_project_out_dir(project_id))
    polish = polish_text(manuscript, title=project["title"], mode=mode, out_dir=out_dir)
    project["files"] = polish["files"]
    project["result"] = {**(project.get("result") or {}), "polished_markdown": polish["polished_markdown"],
                         "coverage": polish["coverage"], "qa": polish["qa"], "files": polish["files"],
                         "chapters": chapters}
    _persist_project(project)
    return {"project_id": project_id, "idx": idx, "ok": polish["ok"],
            "content_md": target["content_md"], "coverage": polish["coverage"]}


def add_source(project_id: str, source_id: str, text: str, uri: str = "") -> dict:
    """RAG 자료 추가."""
    project = _PROJECTS.get(project_id)
    if project is None:
        raise KeyError(f"unknown project_id: {project_id}")
    project.setdefault("sources", []).append({"id": source_id, "text": text, "uri": uri})
    _persist_project(project)
    return {"project_id": project_id, "sources": len(project["sources"])}


def get_download_path(project_id: str, fmt: str) -> str | None:
    """프로젝트 산출물 파일 경로(다운로드용)."""
    project = _PROJECTS.get(project_id)
    if project is None:
        return None
    return (project.get("files") or {}).get(fmt)


def _summarize_description(project: dict, limit: int = 300) -> str:
    """챕터 본문(서론 등)에서 소개문 후보를 추출. 프런트매터/헤딩은 제외."""
    result = project.get("result") or {}
    chapters = project.get("chapters") or result.get("chapters") or []
    paras: list[str] = []
    for ch in chapters:
        body = (ch.get("content_md") or "").strip()
        for line in body.splitlines():
            s = line.strip().lstrip("#").strip()
            if not s:
                continue
            paras.append(s)
        if sum(len(p) for p in paras) >= limit:
            break
    text = " ".join(paras).strip().replace("#", "")
    return text[:limit] if text else project.get("topic", "")


def export_extension_profile(project_id: str) -> dict | None:
    """프로젝트 메타데이터를 크롬 확장(oces_profile) 형태로 내보낸다.

    확장 옵션 페이지의 '기본정보'와 동일 키. 민감정보는 포함하지 않는다.
    스튜디오에서 생성한 책 정보를 확장으로 1클릭 이전(내보내기→가져오기)하는 데 사용.
    """
    project = _PROJECTS.get(project_id)
    if project is None:
        return None
    return {
        "title": project.get("title", ""),
        "subtitle": project.get("subtitle", ""),
        "author": project.get("author", ""),
        "pen_name": project.get("pen_name", ""),
        "language": project.get("language", "ko"),
        "short_description": project.get("topic", ""),
        "description": _summarize_description(project),
        "keywords": project.get("keywords", []),
        "categories": project.get("categories", []),
        "price_krw": str(project.get("price_krw", "") or ""),
        "price_usd": str(project.get("price_usd", "") or ""),
        "isbn_ebook": project.get("isbn_ebook", ""),
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
        out_dir = str(_project_out_dir(project_id))
        result = polish_text(manuscript, title=project["title"], mode=mode, out_dir=out_dir)
        project["files"] = result.get("files", {})
        project["result"] = result
        project["status"] = "ready" if result["ok"] else "blocked"
        usage_mod.tracker.record(project.get("user_id", "public"),
                                 tokens=usage_mod.estimate_tokens(result.get("polished_markdown", "")),
                                 books=1)
        _persist_project(project)
    elif project.get("topic"):
        # 원고가 없고 주제가 있으면 OCES 생성→윤문 풀 파이프라인
        project["status"] = "composing"
        result = compose_project(project_id, mode=mode)
    else:
        project["status"] = "started"
        return {"project_id": project_id, "status": "started", "note": "원고/주제가 없어 대기"}

    return {
        "project_id": project_id,
        "status": project["status"],
        "ok": result["ok"],
        "coverage_ok": (result.get("coverage") or {}).get("ok"),
        "qa_ok": (result.get("qa") or {}).get("ok"),
        "result": result,
    }


# 모듈 로드 시 영속 저장소에서 프로젝트 복원(재시작 복구)
_load_from_store()
