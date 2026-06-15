"""OneClick eBook Studio API (FastAPI).

oneclick-ebook-studio 의 v0 스켈레톤을 계승하되, 더미 TODO 를 실제 엔진 호출로 교체.
비즈니스 로직은 service.py(프레임워크 비의존)에 있으며 여기서는 HTTP 바인딩만 한다.

실행:
  cd apps/studio_api
  pip install -r requirements.txt
  uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import json
import time

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel


import auth as auth_mod
import jobs as jobs_mod
import service


def _uid(x_user: str | None, authorization: str | None = None) -> str:
    """사용자 스코프 결정. Authorization: Bearer JWT 우선, 없으면 X-User, 없으면 public."""
    token = auth_mod.parse_bearer(authorization)
    if token:
        try:
            return auth_mod.user_from_token(token)
        except ValueError:
            pass
    return (x_user or "public").strip() or "public"

app = FastAPI(title="OneClick eBook Studio API", version="1.0")

# 로컬 웹 프론트(studio_web)에서 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProjectIn(BaseModel):
    title: str
    topic: str = ""
    genre: str = ""
    author: str = ""
    audience: str = ""
    tone: str = ""
    language: str = "ko"
    length_target: int = 6000
    n_chapters: int = 6


class PolishIn(BaseModel):
    text: str
    title: str = "manuscript"
    mode: str = "rules"


class ComposeIn(BaseModel):
    project_id: str
    manuscript: str = ""
    mode: str = "rules"


class ComposeBookIn(BaseModel):
    title: str
    topic: str
    n_chapters: int = 6
    length_target: int = 6000
    language: str = "ko"
    provider: str = "stub"
    mode: str = "rules"


@app.get("/health")
def health():
    return service.health()


class TokenIn(BaseModel):
    user_id: str
    exp_seconds: int = 86400


@app.post("/api/auth/token")
def issue_token(t: TokenIn):
    """개발용 JWT(HS256) 발급. 운영은 실제 IdP 연동으로 대체."""
    if not t.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id required")
    return {"access_token": auth_mod.make_token(t.user_id.strip(), exp_seconds=t.exp_seconds),
            "token_type": "bearer"}


@app.post("/api/projects")
def create_project(p: ProjectIn, x_user: str | None = Header(default=None),
                   authorization: str | None = Header(default=None)):
    try:
        return service.create_project(
            p.title, p.topic, p.genre, p.author, audience=p.audience, tone=p.tone,
            language=p.language, length_target=p.length_target, n_chapters=p.n_chapters,
            user_id=_uid(x_user, authorization))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/projects")
def list_projects(x_user: str | None = Header(default=None),
                  authorization: str | None = Header(default=None)):
    return {"projects": service.list_projects(user_id=_uid(x_user, authorization))}


@app.get("/api/projects/{project_id}")
def get_project(project_id: str, x_user: str | None = Header(default=None),
                authorization: str | None = Header(default=None)):
    project = service.get_project(project_id, user_id=_uid(x_user, authorization))
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@app.post("/api/polish")
def polish(p: PolishIn):
    try:
        return service.polish_text(p.text, title=p.title, mode=p.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/compose/start")
def compose_start(c: ComposeIn):
    try:
        return service.compose_start(c.project_id, c.manuscript, c.mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/compose/book")
def compose_book(c: ComposeBookIn):
    """제목+주제 → 목차→집필→윤문→EPUB 풀 파이프라인(OCES, 동기)."""
    try:
        return service.compose_book(
            c.title, c.topic, n_chapters=c.n_chapters, length_target=c.length_target,
            language=c.language, provider=c.provider, mode=c.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class JobStartIn(BaseModel):
    provider: str = "stub"
    mode: str = "rules"


class RegenerateIn(BaseModel):
    project_id: str
    idx: int
    provider: str = "stub"
    mode: str = "rules"


class SourceIn(BaseModel):
    source_id: str
    text: str
    uri: str = ""


@app.post("/api/projects/{project_id}/compose")
def compose_project_async(project_id: str, body: JobStartIn | None = None):
    """비동기 컴포즈 잡 시작 → {job_id}. 진행은 /api/jobs/{id} 또는 SSE 로 조회."""
    body = body or JobStartIn()
    try:
        return service.start_compose_job(project_id, provider=body.provider, mode=body.mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.get("/api/jobs/{job_id}/stream")
def stream_job(job_id: str):
    """SSE 진행 스트림. 이벤트 발생분을 순차 전송, 종료 상태면 닫는다."""
    if service.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")

    def gen():
        sent = 0
        for _ in range(600):  # 최대 ~60초 폴링 가드
            job = service.get_job(job_id)
            events = job.get("events", []) if job else []
            while sent < len(events):
                yield jobs_mod.sse_format(events[sent])
                sent += 1
            if job and job.get("state") in ("done", "failed"):
                break
            time.sleep(0.1)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/projects/{project_id}/outline")
def get_outline(project_id: str):
    project = service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return {"outline": project.get("outline", [])}


@app.get("/api/projects/{project_id}/chapters")
def get_chapters(project_id: str):
    project = service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return {"chapters": project.get("chapters", [])}


@app.post("/api/chapters/regenerate")
def regenerate_chapter(r: RegenerateIn):
    try:
        return service.regenerate_chapter(r.project_id, r.idx, provider=r.provider, mode=r.mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class ChapterEditIn(BaseModel):
    project_id: str
    idx: int
    content_md: str
    mode: str = "rules"


@app.patch("/api/chapters")
def edit_chapter(e: ChapterEditIn):
    """챕터 인라인 편집(자동저장) → 재조립·재윤문·재출력."""
    try:
        return service.edit_chapter(e.project_id, e.idx, e.content_md, mode=e.mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/jobs/{job_id}/pause")
def pause_job(job_id: str):
    try:
        return service.pause_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/jobs/{job_id}/resume")
def resume_job(job_id: str):
    try:
        return service.resume_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/projects/{project_id}/extension-profile")
def extension_profile(project_id: str, x_user: str | None = Header(default=None),
                      authorization: str | None = Header(default=None)):
    """스튜디오 책 메타데이터를 크롬 확장(oces_profile) 형태로 내보냄(1클릭 연동용)."""
    if service.get_project(project_id, user_id=_uid(x_user, authorization)) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return service.export_extension_profile(project_id)


@app.get("/api/usage")
def get_usage(x_user: str | None = Header(default=None),
              authorization: str | None = Header(default=None)):
    return service.get_usage(_uid(x_user, authorization))


@app.get("/api/usage/dashboard")
def usage_dashboard():
    return service.usage_dashboard()


@app.post("/api/projects/{project_id}/sources")
def add_source(project_id: str, s: SourceIn):
    try:
        return service.add_source(project_id, s.source_id, s.text, s.uri)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/projects/{project_id}/download/{fmt}")
def download(project_id: str, fmt: str):
    path = service.get_download_path(project_id, fmt)
    if not path:
        raise HTTPException(status_code=404, detail="artifact not found")
    media = {"md": "text/markdown", "epub": "application/epub+zip",
             "html": "text/html", "pdf": "application/pdf"}.get(fmt, "application/octet-stream")
    filename = f"{project_id}.{fmt}"
    return FileResponse(path, media_type=media, filename=filename)
