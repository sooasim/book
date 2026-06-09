# 전자책 자동 출판 · 윤문기 통합 시스템 (Ink&Press)

작성일: 2026-06-08

이 저장소는 **원고를 윤문(다듬기)하고 전자책으로 변환해 국내외 플랫폼에 반복 등록**하는
통합 시스템의 기획·설계·기술백서와, 이미 동작하는 출판 보조 프로그램(MVP)을 담는다.

시스템 코드명: **Ink&Press** (한국어: `전자책 원클릭 출판센터 + 윤문기`)

```
원고 초안  ──▶  [윤문기 Refiner]  ──▶  [변환 Builder]  ──▶  [검수 Reviewer]  ──▶  [출판 Publisher]
 (.docx/.md)     맞춤법·문체·일관성      EPUB/PDF 생성       EPUBCheck·미리보기      플랫폼별 제출팩/자동입력
```

## 이 저장소의 두 축

| 구분 | 위치 | 상태 | 설명 |
|---|---|---|---|
| **신규 기획·아키텍처 백서** | [`docs/`](docs/) | 신규 작성 | 자동 출판 **+ 윤문기**를 통합한 제품 기획서, 시스템 아키텍처 기술백서, 윤문기 엔진 상세설계, 데이터 모델/API, 로드맵 |
| **출판 보조 프로그램(기존 MVP)** | [`apps/ebook_publisher/`](apps/ebook_publisher/) | 동작하는 MVP | 14개 국내외 플랫폼 레지스트리, 메타데이터→제출팩 생성기, 로컬 대시보드, 반매크로 |
| **윤문 엔진 v3 (원장 기반 무손실)** | [`apps/ebook_polisher/`](apps/ebook_polisher/) | **동작·테스트 85개 통과** | 페이지/블록 원장, Coverage Gate, 무손실 윤문, 7-Agency, CLI 원클릭 |
| **OneClick eBook Studio (풀 제품)** | [`apps/studio_api/`](apps/studio_api/) · [`apps/studio_web/`](apps/studio_web/) | **동작·테스트 31개 통과** | 제목+주제→목차→집필→윤문→EPUB. 비동기 잡·SSE·챕터 재생성·RAG·다운로드 + 제품 UI/UX |

## 무엇이 새로 추가되었나 — 윤문기(Refiner)

기존 MVP는 "완성된 원고를 플랫폼에 등록"하는 **뒷단(출판)** 만 다뤘다.
이번 기획은 그 앞에 **윤문기(Refiner)** 를 붙여, *초고 → 판매 가능한 전자책* 전체를 잇는다.

윤문기는 다음을 자동화한다(사람 승인 게이트 유지).

- 맞춤법·띄어쓰기·문장부호 교정
- 문체/어조 일관화(존댓말/평서체, 1인칭/3인칭 등)
- 중복·군더더기 제거, 가독성 향상(문장 길이·수동태)
- 용어/표기 일관성(인명·고유명사·전문용어 사전)
- 장/절 구조 정리와 목차(TOC) 생성
- 변경 이력(diff)과 근거를 남겨 **사람이 수락/거절**

### ⚠ 필수: 600항목 윤문 체크리스트 (Hard Gate)

모든 윤문 실행은 [`resources/checklist/`](resources/checklist/)의 **출판용 AI 원고 윤문·교정·교열 체크리스트 600항목**을
**빠짐없이 전수 적용**한다. 600항목 점검(`checklist_run.json`)이 완료(`pending==0 && fail==0`)되기 전에는
**변환·검수·출판 단계로 진행할 수 없다**(`ComplianceGate.checklist_incomplete`로 강제).
원본 Markdown이 단일 진실원이며, `apps/ebook_publisher/scripts/build_checklist.py`로 기계용 JSON을 재생성한다.

### 🚀 아키텍처 v2.0 — 제로존 방법론 통합 (자율형 출판 엔진)

대형·고정합 원고(수천 페이지)를 위해 윤문기를 **다중 에이전트·다중 사이클 자율 엔진**으로 확장한다.
상세: [`docs/06_아키텍처v2_제로존방법론통합백서.md`](docs/06_아키텍처v2_제로존방법론통합백서.md).

- **7-Agency 교차검증**: 논리/팩트(A·B·C)·정직성(E)·응축(F)·윤문(G)·집행관(J).
- **정직 봉인(Honest Boxing)**: `★`(확신)/`◑`(주의) 마커 — 인간은 `◑`만 결재(Sign-off).
- **메타 좌표(Lemma) 동기화**: 의존성 그래프로 1페이지 변경을 전권 전수 동기화.
- **Hard-Fail 게이트**: 금지어·괄호/마크다운 깨짐·빈 청크를 통과 못 하면 강제 재작업.
  → 실제 동작 린터 [`apps/ebook_publisher/scripts/lint_text.py`](apps/ebook_publisher/scripts/lint_text.py)
  (`python3 apps/ebook_publisher/scripts/lint_text.py --selftest`), 금지어 사전 [`resources/hardfail/`](resources/hardfail/).

## 빠른 시작 — 기존 출판 MVP 실행

```powershell
# Windows / PowerShell
powershell -ExecutionPolicy Bypass -File .\apps\ebook_publisher\RUN_PUBLISHER_DASHBOARD.ps1
# 브라우저: http://127.0.0.1:8765
```

```bash
# macOS / Linux (서버만)
python3 apps/ebook_publisher/app.py
```

## 문서 읽는 순서

1. [`docs/00_제품기획서.md`](docs/00_제품기획서.md) — 무엇을, 왜, 누구를 위해
2. [`docs/01_시스템아키텍처_기술백서.md`](docs/01_시스템아키텍처_기술백서.md) — 전체 구조·기술 선택·근거
3. [`docs/02_윤문기엔진_상세설계서.md`](docs/02_윤문기엔진_상세설계서.md) — 신규 핵심 모듈
4. [`docs/03_자동출판_파이프라인_설계서.md`](docs/03_자동출판_파이프라인_설계서.md) — 변환·검수·등록
5. [`docs/04_데이터모델_및_API명세.md`](docs/04_데이터모델_및_API명세.md) — 스키마·REST API
6. [`docs/05_개발로드맵_및_품질기준.md`](docs/05_개발로드맵_및_품질기준.md) — 단계·완료 기준

## 설계 대원칙 (안전 경계)

이 시스템은 **반복 노동과 자료 준비를 자동화**하되, 법적 책임이 따르는 지점은 사람이 확정한다.

- 자동화하지 않음: 회원가입 최종 완료, 비밀번호 입력, 본인인증, CAPTCHA, 약관 동의,
  독점 계약/KDP Select 선택, 세금·정산 정보 저장, **최종 출판 버튼**.
- 윤문기는 원문 의미를 바꾸는 제안을 **자동 확정하지 않고** 사람이 검토하도록 diff로 제시한다.
- 모든 AI 생성/보정 결과는 플랫폼 정책에 맞춰 **AI 사용 고지** 상태를 추적한다.

자세한 내용은 각 문서를 참고한다.
