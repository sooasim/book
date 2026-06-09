# 고도화 — Claude 경로·PDF 기본 탑재·JWT 인증·잡 영속화·표지 PNG/삽화

작성일: 2026-06-09

---

## 1. 추가된 것

| 영역 | 구현 | 위치 |
|---|---|---|
| Claude 경로(주입식, 테스트 가능) | `AnthropicProvider(client=...)` + 단계별 모델 라우팅 | `ebook_polisher/llm_provider.py` |
| PDF 기본 탑재(의존성 0) | stdlib `minipdf` + reportlab 폴백 | `ebook_polisher/minipdf.py`, `export.py` |
| JWT(HS256) 인증 | stdlib JWT + Bearer 스코프 | `studio_api/auth.py`, `main.py` |
| 잡 이벤트 영속화 + 재시작 복구 | JobStore persister/load → SQLite | `studio_api/jobs.py`, `service.py` |
| 표지 PNG 래스터화 | stdlib zlib PNG(결정적) | `ebook_polisher/cover.py` |
| 삽화 생성 스텁 | `Provider.image()`(Stub 결정적/Claude 스켈레톤) | `llm_provider.py` |

## 2. Claude 경로 (provider-agnostic)

- `AnthropicProvider`는 `client` 주입을 받아 **네트워크 없이 단위 테스트** 가능. 단계별 모델 라우팅
  (outline/edit→Opus, write/factqa→Sonnet)을 검증.
- 키가 있으면 `anthropic` SDK로 `messages.create` 호출(실서비스), 없으면 명확한 RuntimeError → StubProvider 사용.
- 기본은 여전히 오프라인 결정적 StubProvider라 키 없이 전 기능 동작.

## 3. PDF 기본 탑재 (오프라인)

- `minipdf.write_pdf`: 표준 라이브러리만으로 유효한 PDF(`%PDF-1.4`, xref/trailer, Helvetica) 생성 — **설치 없이 항상 PDF 다운로드 가능**.
- `export.export_pdf`: reportlab/weasyprint 있으면 고품질(CJK/스타일), 없으면 minipdf 폴백.
- `available_formats().pdf == True` 항상, `pdf_quality ∈ {basic, rich}`.
- 한계: base-14 폰트는 한글 글리프가 없어 minipdf PDF의 한글은 '?'로 표기됨 → 한국어는 EPUB 권장, 고품질 PDF는 reportlab+CJK 폰트/ weasyprint로 업그레이드.

## 4. JWT 인증 + 멀티테넌시

- `POST /api/auth/token {user_id}` → HS256 JWT 발급(`OCES_SECRET`).
- 요청은 `Authorization: Bearer <jwt>` 우선, 없으면 `X-User`, 없으면 `public`으로 스코프.
- 프로젝트/사용량이 사용자별 격리.

## 5. 잡 영속화 + 재시작 복구

- `JobStore.set_persister(STORE.save_job)` → create/append_event/set 마다 SQLite 저장(이벤트 포함).
- 기동 시 `JOBS.load(STORE.load_jobs())` 로 복구. **프로세스 재시작에도 잡·진행 이벤트 보존**(테스트로 검증).

## 6. 표지 PNG + 삽화 스텁

- `cover.cover_png(title)`: 제목 해시 기반 결정적 그라데이션 PNG(zlib). 산출물 `cover_png` 다운로드.
- `Provider.image(prompt, seed)`: Stub은 결정적 PNG, Claude는 이미지 모델 연결 스켈레톤.

## 7. UI

- 헤더에 **로그인 바**(사용자 ID → JWT 발급, X-User/Bearer 자동 전송).
- 결과 패널 다운로드에 **PDF** 포함(표지 PNG는 cover_png 산출).

## 8. 검증

- 엔진 206(+2 skip) + 스튜디오 75 = **281 테스트 통과**.
- 신규: Claude 주입 모킹, PDF 폴백/유효성, JWT 라운드트립·변조·만료, 잡 재시작 복구, 표지 PNG.

## 9. 다음 단계

- reportlab + 나눔/노토 CJK 폰트로 고품질 한글 PDF, weasyprint(HTML→PDF) 옵션.
- 실제 이미지 모델 연결(삽화 자동 배치, LayoutAgent).
- 잡 재개 시 컨텍스트 영속화로 중간부터 재개(현재는 결정적 전체 재실행).
