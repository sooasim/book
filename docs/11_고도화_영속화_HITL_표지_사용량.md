# 고도화 — 영속화·HITL 일시정지/재개·인라인 편집·표지·멀티테넌시·비용 대시보드

작성일: 2026-06-09
참고: OCES `oces/02-architecture.md`(§3 스키마·§5 상태머신·§7 보안), `04-product-plan.md`(§4 기능)

---

## 1. 추가된 것

| 영역 | 구현 | 위치 |
|---|---|---|
| 영속화(SQLite, PG 승격경로) | 프로젝트 저장/복원, 재시작 복구 | `studio_api/persistence.py` |
| HITL 일시정지/재개 | 잡 경계 pause + 결정적 resume | `studio_api/jobs.py`, `service.py` |
| 챕터 인라인 편집 | PATCH + 재조립·재윤문 + 자동저장 UI | `service.edit_chapter`, `studio_web` |
| 표지 생성 | 결정적 SVG 표지 → EPUB 삽입 | `ebook_polisher/cover.py`, `epub_export.py` |
| 멀티테넌시 | user_id 스코프(X-User 헤더) | `service.py`, `main.py` |
| 비용/사용량 대시보드 | 토큰·권수 집계, 쿼터 | `studio_api/usage.py`, `/api/usage*` |
| PDF/DOCX 출력 | 라이브러리 가용 시 활성 | `ebook_polisher/export.py` |

## 2. 영속화 (OCES 02 §3)

- `persistence.Store`(SQLite): `projects`/`jobs` 테이블에 JSON 문서로 upsert. 동일 스키마라 PostgreSQL로 그대로 승격.
- 서비스는 모든 프로젝트 변경 시 `_persist_project`로 저장하고, 모듈 로드 시 `_load_from_store`로 복원 → **프로세스 재시작에도 프로젝트 보존**.
- 경로는 `OCES_DB` 환경변수(기본 `:memory:`; 운영은 파일/PG).

## 3. HITL 일시정지/재개 (OCES 02 §5)

- `POST /api/jobs/{id}/pause` → 다음 단계 경계에서 `paused`로 정지(체크포인트 저장).
- `POST /api/jobs/{id}/resume` → 재개. `rules` 모드가 결정적이라 동일 산출을 보장하며 처음부터 안전 재실행.
- 잡이 reset/삭제되어도 데몬 스레드가 조용히 종료(견고성).

## 4. 챕터 인라인 편집 (OCES 04 §4.2)

- `PATCH /api/chapters {project_id, idx, content_md}` → 챕터 본문 교체 → 원고 재조립 → 재윤문 → 산출물 재생성.
- UI: 챕터를 펼쳐 직접 수정하면 **800ms 디바운스 자동저장**("저장 중…/✓ 저장됨").

## 5. 표지 생성

- `cover.cover_svg(title, author)` — 제목 해시 기반 색상의 결정적 SVG 표지(외부 라이브러리 불필요).
- EPUB의 첫 spine 항목으로 `cover.xhtml`(인라인 SVG) 삽입. `cover.svg`도 별도 산출.
- UI에 표지 미리보기 표시.

## 6. 멀티테넌시 + 비용 대시보드 (OCES 02 §7, 04 §5)

- `X-User` 헤더로 사용자 식별(기본 `public`). 프로젝트는 소유자 스코프(목록/조회 격리).
- `usage.UsageTracker` — 사용자별 토큰·권수 누적, 기본 쿼터(2M), `over_quota`.
- `GET /api/usage`(현재 사용자), `GET /api/usage/dashboard`(전체 집계). UI에 사용량 배지.

## 7. UI/UX 추가

- 진행 중 **⏸ 일시정지 / ▶ 재개** 버튼.
- 결과 패널: **표지 미리보기**, EPUB/PDF/DOCX/MD/HTML 다운로드, **챕터 펼침 편집(자동저장)** + 재생성, 사용량 배지.

## 8. 검증

- 엔진 173(+2 skip) + 스튜디오 64 = **237 테스트 통과**.
- 신규 테스트: 인라인 편집, pause→resume 완료, 사용량 집계, 멀티테넌시 격리, 영속화 라운드트립, 표지 EPUB 삽입.

## 9. 다음 단계

- 실제 LLM(Claude) 경로 통합 테스트(키 주입 환경), PDF 렌더러 기본 탑재(reportlab).
- 잡 이벤트 영속화 + 재시작 시 잡 복구, JWT 인증, 결제/쿼터 상향.
- 표지 래스터화(PNG)·삽화 생성(이미지 모델 연결).
