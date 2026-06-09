# OneClick eBook Studio — 구현 가이드 (Implementation Guide)

문서 버전: 1.0 · 상태: Draft

> "다른 곳에서 처음부터 구축"할 때 따라갈 수 있는 실전 빌드 순서. 현 리포지토리 스택을 출발점으로 한다.

---

## 1. 권장 스택 (현 리포 기준 확장)

| 영역 | 기술 |
|------|------|
| API | FastAPI · Python 3.11 · pydantic v2 · uvicorn |
| Web | Next.js 16 (App Router) · React 19 · Tailwind 4 |
| 잡 큐 | Redis + Arq (경량) 또는 Celery |
| DB | PostgreSQL + SQLAlchemy/SQLModel + Alembic |
| 벡터 | pgvector (단순) 또는 Qdrant |
| 스토리지 | S3 호환 (Cloudflare R2 / MinIO) |
| 렌더 | pandoc / ebooklib / WeasyPrint |
| LLM | Provider 추상화 (기본 Anthropic Claude 권장) |
| 배포 | Docker → Railway(현재) → K8s |

## 2. 모노레포 구조(제안)

```
oneclick-ebook-studio/
├─ apps/
│  ├─ studio-api/         # FastAPI (현존)
│  │  ├─ app/
│  │  │  ├─ main.py             # 라우터 등록
│  │  │  ├─ routers/            # projects, jobs, exports
│  │  │  ├─ models/             # SQLModel 엔티티
│  │  │  ├─ schemas/            # pydantic I/O
│  │  │  ├─ orchestrator/       # 상태머신 + 단계 실행
│  │  │  ├─ agents/             # outline/writer/editor/factqa/layout/export
│  │  │  ├─ llm/                # provider 추상화, 라우팅, 캐싱
│  │  │  ├─ rag/                # 임베딩/검색
│  │  │  ├─ render/             # epub/pdf/docx 렌더러
│  │  │  └─ worker.py           # 큐 워커 엔트리
│  │  └─ tests/
│  └─ studio-web/         # Next.js (현존)
│     └─ app/             # 대시보드/생성/진행/에디터/내보내기
├─ docs/                  # 본 문서 묶음
└─ infra/                 # docker-compose, k8s 매니페스트
```

> 현재 `apps/studio-api`에 가상환경(`.venv`)과 `새 텍스트 문서.txt` 등 불필요 파일이 커밋되어 있다.
> 재구축 시 `.gitignore`에 `.venv/`, `__pycache__/`, `node_modules/` 추가 권장.

## 3. 단계별 빌드 순서

### Step 1 — 데이터 계층
1. PostgreSQL 연결 + SQLModel 엔티티(`projects, jobs, outlines, chapters, artifacts, events`).
2. Alembic 마이그레이션.
3. 현 스텁 `POST /api/projects`를 실제 영속화로 교체.

### Step 2 — LLM Provider 추상화
```python
class LLMProvider(Protocol):
    def complete(self, system: str, user: str, *, schema=None,
                 max_tokens=None, model_tier="standard") -> Completion: ...
    def embed(self, text: str) -> list[float]: ...
```
- 기본 구현: Anthropic. 라우팅 정책(단계별 티어)·캐싱·폴백 포함.

### Step 3 — 단계 에이전트 (동기 v1)
1. `OutlineAgent` → 구조화 출력(JSON 스키마) 목차.
2. `WriterAgent` → running-summary 캐리오버 집필.
3. Markdown 병합 → `render/epub.py`로 EPUB.
4. `POST /api/projects/{id}/compose` 동기 실행으로 end-to-end 1권 생성.

### Step 4 — 비동기화 (v2)
1. Redis + Arq 워커, `jobs` 상태머신, 체크포인트.
2. `compose`는 enqueue 후 `job_id` 반환(현 `/api/compose/start` 확장).
3. `GET /api/jobs/{id}/stream` SSE 진행 이벤트.

### Step 5 — 품질 게이트 + HITL (v2)
1. `EditorAgent`(전역 교정), `FactQAAgent`(검사 게이트).
2. 자동 수정 루프(self-refine) + 사람 개입 일시정지/재개.
3. 챕터 단위 재생성 API.

### Step 6 — 확장 (v3+)
- RAG 업로드, 이미지 생성, Style Bible UI, 결제/쿼터, 다국어.

## 4. 로컬 개발 (docker-compose 스케치)

```yaml
services:
  api:     # FastAPI (uvicorn app.main:app)
  worker:  # 동일 이미지, command: python -m app.worker
  web:     # Next.js dev
  db:      # postgres + pgvector
  redis:   # 큐/캐시
  minio:   # S3 호환 스토리지
```

## 5. 환경 변수
```
DATABASE_URL, REDIS_URL
S3_ENDPOINT, S3_KEY, S3_SECRET, S3_BUCKET
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
EMBEDDING_MODEL=...
TOKEN_BUDGET_PER_BOOK=..., MAX_STAGE_RETRIES=3
```

## 6. 테스트 전략
- **유닛**: 에이전트 입출력 스키마, 분량 배분, 용어 정규화.
- **계약(contract)**: API 스키마(pydantic) 회귀.
- **파이프라인 회귀**: 고정 주제 셋으로 품질 지표 추적(임계 가드).
- **LLM 호출 모킹**: 결정적 테스트 위해 provider 더블 사용.

## 7. 배포 노트 (현 리포 반영)
- `studio-api/Dockerfile.txt`, `studio-web/Dockerfile.txt` → 실제 `Dockerfile`로 이름 변경 필요.
- Railway는 Python 3.11 핀(`.tool-versions`) 사용 중. Worker는 별도 서비스로 분리 배포.
- Web `app/layout.tsx`의 메타데이터/제목이 아직 "Create Next App" 기본값 → 브랜딩 교체 필요.

## 8. 즉시 정리할 기술 부채 (현 v0)
- [ ] `.venv/`, `__pycache__/` 커밋 제거 + `.gitignore` 추가
- [ ] `새 텍스트 문서.txt`(빈 파일) 제거
- [ ] `Dockerfile.txt` → `Dockerfile` 리네임
- [ ] Web 기본 스캐폴드 → 실제 화면으로 교체
- [ ] API 스텁 → DB 영속화 + 잡 큐 연결
