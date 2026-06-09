# 고도화 — 비동기 잡·SSE·챕터 재생성·RAG·다중 포맷·UI/UX

작성일: 2026-06-09
참고: OCES `oces/02-architecture.md`(§4 API, §5 상태머신), `oces/03-algorithms.md`(§3.4 RAG, §8 오케스트레이터)

---

## 1. 추가된 것 (OCES v2/v3 항목 구현)

| 영역 | 구현 | 위치 |
|---|---|---|
| 비동기 잡 + 상태머신 | `JobStore` + `execute_stages` + `run_in_thread`(스레드) | `studio_api/jobs.py` |
| SSE 진행 스트림 | `GET /api/jobs/{id}/stream` (event/data 와이어) | `studio_api/main.py` |
| 챕터 단위 재생성 | `regenerate_chapter` + `POST /api/chapters/regenerate` | `studio_api/service.py` |
| RAG(근거 기반) | 인메모리 벡터스토어 + 브리프 컨텍스트 주입 | `ebook_polisher/rag.py` |
| 다중 포맷 출력 | EPUB/HTML(기본) + PDF/DOCX(라이브러리 있으면) | `ebook_polisher/export.py` |
| 다운로드 | `GET /api/projects/{id}/download/{fmt}` (FileResponse) | `studio_api/main.py` |
| **UI/UX** | 폼 → 진행 타임라인 → 결과(목차/QA/다운로드/재생성) | `studio_web/app/*` |

## 2. 잡 상태머신 (OCES 02 §5)

```
queued → running → (stage loop: outline → write → edit → export) → done | failed
```
- 각 단계 전이마다 `checkpoint` 저장 + 이벤트(`stage_started`/`stage_done`/`job_done`/`error`) 기록.
- 단계 실패 시 `failed` + error 이벤트(재시도/HITL 확장 지점).
- `POST /api/projects/{id}/compose` → `{job_id}` 즉시 반환(무상태 API + 백그라운드 워커 스레드).
- 진행 조회: `GET /api/jobs/{id}`(폴링) 또는 `GET /api/jobs/{id}/stream`(SSE).

## 3. 챕터 재생성

`POST /api/chapters/regenerate {project_id, idx}` — 해당 챕터만 재집필(앞 챕터 요약 carryover) →
원고 재조립 → 재윤문 → 산출물 재생성. 부분 수정 비용 최소화(OCES 04 §4.2 SHOULD).

## 4. RAG (근거 고정, 환각 억제)

- `POST /api/projects/{id}/sources` 로 자료 등록.
- compose 시 각 챕터 브리프에 `rag_context`(top-k 유사 자료)를 주입.
- 오프라인 결정적 임베딩(StubProvider 8차원 해시)으로 키 없이 동작, 운영형은 Qdrant/pgvector로 승격.

## 5. UI/UX (studio_web, Next.js 16 + React 19)

```
app/
  page.tsx                 # 전체 플로우 오케스트레이션(생성→폴링→결과)
  lib/api.ts               # 타입드 API 클라이언트
  components/
    ProjectForm.tsx        # 제목/주제/독자/톤/챕터수/분량/엔진/모드
    ProgressTimeline.tsx   # 단계 타임라인 + 진행률 바
    ResultPanel.tsx        # QA 배지·다운로드·목차(챕터 재생성)·윤문본 미리보기
    Badge.tsx
```

사용자 플로우(OCES 04 §3):
1. 폼 입력 → **원클릭 생성**
2. 프로젝트 생성 → 컴포즈 잡 시작 → 진행 타임라인 실시간(폴링)
3. 완료 시 결과: 출판가능/커버리지/QA 배지, EPUB·MD·HTML 다운로드, 목차별 **↻ 재생성**, 윤문본 미리보기

실행:
```bash
cd apps/studio_api && uvicorn main:app --port 8000      # API
cd apps/studio_web && npm install && npm run dev          # http://localhost:3000
```

## 6. 검증

- 엔진 158(+2 skip: docx/pdf 미설치) + 스튜디오 31 = **189 테스트 통과**.
- 비동기 잡 엔드투엔드(스레드 완료, progress 1.0, 단계 이벤트), 챕터 재생성, RAG 주입, 다운로드 경로 테스트 포함.
- PDF/DOCX는 라이브러리 설치 시 자동 활성(available_formats 반영), 미설치 시 graceful.

## 7. 다음 단계

- 잡 영속화(PostgreSQL `jobs/events`) + 재시작 복구, HITL 일시정지/재개 API 연결.
- 에디터 인라인 편집(PATCH chapters) + 자동저장.
- 표지/삽화 이미지 생성(LayoutAgent), PDF 렌더러 기본 탑재.
- 멀티테넌시/인증/쿼터(OCES 02 §7), 비용·토큰 대시보드.
