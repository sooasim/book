# OneClick eBook Studio — 시스템 아키텍처 (Architecture)

문서 버전: 1.0 · 상태: Draft

---

## 1. 아키텍처 개요

OCES는 **3-tier + 비동기 오케스트레이션** 구조다.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Client Tier — Next.js 16 (App Router, React 19)                     │
│   - 프로젝트 생성/설정 UI   - 진행 스트리밍(SSE)   - 미리보기/다운로드 │
└───────────────┬─────────────────────────────────────────────────────┘
                │ HTTPS (REST + SSE)
┌───────────────▼─────────────────────────────────────────────────────┐
│  API Tier — FastAPI (Python 3.11)                                    │
│   - 인증/권한   - 프로젝트 CRUD   - 잡 enqueue/조회   - 산출물 서명URL  │
│   - 무상태(stateless). 장시간 작업은 큐로 위임.                        │
└───────┬───────────────────────────────┬─────────────────────────────┘
        │ enqueue(job)                  │ read/write
┌───────▼──────────┐          ┌─────────▼──────────────────────────────┐
│  Job Queue        │          │  Data Tier                              │
│  (Redis + Arq/    │          │   - PostgreSQL (프로젝트/잡/사용자)      │
│   Celery)         │          │   - Vector Store (pgvector/Qdrant)      │
└───────┬──────────┘          │   - Object Storage (S3/R2: 산출물)      │
        │ dequeue              └─────────────────────────────────────────┘
┌───────▼──────────────────────────────────────────────────────────────┐
│  Orchestration Tier — Worker(s)                                       │
│   Orchestrator(상태머신) → Stage Agents → LLM Provider Layer          │
└───────────────────────────────────────┬─────────────────────────────┘
                                         │
                          ┌──────────────▼──────────────┐
                          │  LLM Provider Layer          │
                          │  Anthropic / OpenAI / local  │
                          │  + Embedding + (옵션)Image    │
                          └──────────────────────────────┘
```

## 2. 컴포넌트 책임 (Components)

### 2.1 Web (studio-web)
- **역할**: 입력 폼(제목/주제/옵션), 진행 상황 실시간 표시, 챕터 미리보기/편집, 산출물 다운로드.
- **핵심 화면**: 대시보드 / 프로젝트 생성 / 컴포즈 진행(스트리밍) / 에디터 / 내보내기.
- **통신**: REST(CRUD) + **SSE**(진행 이벤트). 편집 자동저장은 debounce PATCH.

### 2.2 API (studio-api)
- **역할**: 외부 진입점. 인증, 검증, 프로젝트/잡 관리, 산출물 서명 URL 발급.
- **무상태 원칙**: 모든 장시간 연산은 잡 큐로 위임하고 즉시 `job_id` 반환.

### 2.3 Orchestrator (Worker)
- **역할**: 잡을 받아 **단계 상태머신**을 구동. 각 단계는 멱등(idempotent)·재시도 가능·체크포인트 저장.
- 자세한 단계/알고리즘은 [03-algorithms.md](./03-algorithms.md).

### 2.4 Stage Agents
- `OutlineAgent`, `WriterAgent`, `EditorAgent`, `FactQAAgent`, `LayoutAgent`, `ExportAgent`.
- 각 에이전트는 (프롬프트 템플릿 + 도구 + 검증기) 단위. 입력/출력 스키마가 명확.

### 2.5 LLM Provider Layer
- 모델 호출 추상화: `complete()`, `embed()`, (옵션)`image()`.
- **라우팅 정책**: 단계별 모델 티어(저비용→고품질), 폴백, 토큰 예산 가드, 캐싱.

### 2.6 Data Tier
- **PostgreSQL**: 정형 데이터 + JSONB 메타.
- **Vector Store**: 사용자 업로드 자료 RAG, 챕터 간 의미 검색.
- **Object Storage**: 최종/중간 산출물(.md/.epub/.pdf/.docx/이미지).

## 3. 데이터 모델 (Schema)

```sql
-- 사용자
users(id PK, email UNIQUE, plan, quota_tokens, created_at)

-- 프로젝트: 현재 스텁의 title/topic 확장
projects(
  id PK, user_id FK,
  title text, topic text,
  language text default 'ko',
  audience text,            -- 독자층
  tone text,                -- 톤(전문/친근/학술…)
  length_target int,        -- 목표 단어수
  style_bible jsonb,        -- 용어/금칙어/페르소나/서식 규칙
  status text,              -- draft|composing|ready|failed
  created_at, updated_at
)

-- 잡(오케스트레이션 실행 단위)
jobs(
  id PK, project_id FK,
  type text,                -- compose|regenerate_stage|export
  state text,               -- queued|running|paused|done|failed
  current_stage text,       -- outline|write|edit|factqa|layout|export
  progress numeric,         -- 0..1
  checkpoint jsonb,         -- 재개용 상태 스냅샷
  cost_tokens int,
  error jsonb,
  created_at, updated_at
)

-- 책 구조(SSOT)
outlines(id PK, project_id FK, tree jsonb)         -- 장/절 트리
chapters(
  id PK, project_id FK, idx int,
  title text, brief text,                          -- 집필 지시(목차에서 파생)
  content_md text,                                 -- 본문(Markdown)
  summary text,                                    -- 다음 챕터로 넘길 압축 컨텍스트
  status text,                                     -- pending|drafted|edited|approved
  quality jsonb                                    -- 점수/검사결과
)

-- RAG 자료
sources(id PK, project_id FK, kind, uri, text, embedding vector)

-- 산출물
artifacts(id PK, project_id FK, format, storage_uri, bytes, created_at)

-- 진행 이벤트(SSE 재생/감사)
events(id PK, job_id FK, ts, stage, level, message, payload jsonb)
```

## 4. API 명세 (REST)

현재 스텁(`/health`, `/api/projects`, `/api/compose/start`)을 다음으로 확장:

```
GET    /health                          헬스/레디니스
POST   /api/auth/token                  인증(토큰 발급)

POST   /api/projects                    프로젝트 생성 {title, topic, ...옵션}
GET    /api/projects/{id}               프로젝트 조회
PATCH  /api/projects/{id}               설정/스타일 수정
GET    /api/projects                    목록

POST   /api/projects/{id}/compose       컴포즈 잡 시작 → {job_id}
GET    /api/jobs/{job_id}               잡 상태/진행 폴링
GET    /api/jobs/{job_id}/stream        SSE 진행 스트림
POST   /api/jobs/{job_id}/pause         일시정지(HITL 체크포인트)
POST   /api/jobs/{job_id}/resume        재개

GET    /api/projects/{id}/outline       목차 조회
PUT    /api/projects/{id}/outline       목차 수정(사람 개입)
GET    /api/projects/{id}/chapters      챕터 목록/본문
PATCH  /api/chapters/{cid}              본문 수동 편집
POST   /api/chapters/{cid}/regenerate   특정 챕터만 재생성

POST   /api/projects/{id}/export        {format: epub|pdf|docx|md} → 잡
GET    /api/artifacts/{aid}/download     서명 URL 리다이렉트
```

### 4.1 SSE 이벤트 포맷
```
event: stage_started   data: {"stage":"write","chapter":3,"of":12}
event: token_progress  data: {"stage":"write","chapter":3,"tokens":1840}
event: stage_done      data: {"stage":"write","chapter":3,"quality":{"readability":0.82}}
event: job_done        data: {"job_id":"...","artifacts":[...]}
event: error           data: {"stage":"factqa","message":"...","retryable":true}
```

## 5. 상태머신 (Job State Machine)

```
queued → running → (stage loop) → done
                       │
                       ├─ needs_review → paused → resume → running   (HITL)
                       └─ stage_failed → retry(≤N) → running | failed
```

단계 진행: `outline → write(챕터 루프) → edit → factqa → layout → export`.
각 전이 직전 `checkpoint`를 jobs에 저장 → 워커 크래시 시 마지막 체크포인트에서 재개.

## 6. 인프라 / 배포 (Infra)

- **컨테이너**: API/Web 각각 Dockerfile (현 리포 존재). Worker는 API 이미지 재사용 + 엔트리포인트 분기.
- **현재**: Railway (Python 3.11 핀). **확장**: K8s — API(Deployment+HPA), Worker(큐 길이 기반 오토스케일), Redis/PG 매니지드.
- **환경 변수**(예):
  ```
  DATABASE_URL, REDIS_URL, S3_ENDPOINT/KEY/SECRET/BUCKET,
  LLM_PROVIDER, ANTHROPIC_API_KEY, EMBEDDING_MODEL,
  TOKEN_BUDGET_PER_BOOK, MAX_STAGE_RETRIES
  ```
- **관측성**: 구조적 로그(JSON) + 메트릭(단계 지연/토큰/실패율) + 트레이싱(잡 단위 trace_id).

## 7. 보안 / 컴플라이언스

- 인증: JWT(단기) + 리프레시. API 키는 서버 보관, 클라이언트 미노출.
- 멀티테넌시: 모든 쿼리에 `user_id` 스코프 강제(Row-Level 또는 앱 레벨 가드).
- 산출물 접근: 시간제한 서명 URL.
- 프롬프트 인젝션 방어: 사용자 업로드 자료는 *데이터로만* 취급(시스템 지시와 분리, 신뢰경계 표시).
- PII/저작권: 업로드 자료 보존정책, 표절 검사, 삭제 요청 처리.

## 8. 확장성 / 성능

- **수평 확장**: Worker는 큐 길이 기반 스케일. 챕터 집필은 **병렬화 가능**(단, 일관성 위해 의존 컨텍스트 주입).
- **캐싱**: 동일 프롬프트/임베딩 캐시, LLM 프롬프트 캐싱 활용.
- **백프레셔**: 토큰 예산/동시 잡 한도로 비용·부하 제어.
- **멱등성**: 단계 키(`job_id:stage:chapter`)로 중복 실행 방지.
