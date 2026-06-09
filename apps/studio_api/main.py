"""OneClick eBook Studio API (FastAPI).

oneclick-ebook-studio 의 v0 스켈레톤을 계승하되, 더미 TODO 를 실제 엔진 호출로 교체.
비즈니스 로직은 service.py(프레임워크 비의존)에 있으며 여기서는 HTTP 바인딩만 한다.

실행:
  cd apps/studio_api
  pip install -r requirements.txt
  uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import service

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


@app.post("/api/projects")
def create_project(p: ProjectIn):
    try:
        return service.create_project(p.title, p.topic, p.genre, p.author)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/projects")
def list_projects():
    return {"projects": service.list_projects()}


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    project = service.get_project(project_id)
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
    """제목+주제 → 목차→집필→윤문→EPUB 풀 파이프라인(OCES)."""
    try:
        return service.compose_book(
            c.title, c.topic, n_chapters=c.n_chapters, length_target=c.length_target,
            language=c.language, provider=c.provider, mode=c.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
