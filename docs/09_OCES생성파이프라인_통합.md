# OCES 생성 파이프라인 통합 (제목+주제 → 완성 eBook)

작성일: 2026-06-09
참고 원문: [`oces/`](oces/) (00~05, OneClick eBook Studio 설계 문서 묶음)

---

## 1. 무엇이 추가되었나

기존 우리 엔진은 **윤문(폴리싱)** = "이미 있는 원고를 무손실로 다듬어 출판"하는 *뒤 절반*만 담당했다.
OCES 문서(특히 `oces/03-algorithms.md`)는 **생성(generation)** = "제목+주제만으로 책을 써내는"
*앞 절반*을 정의한다. v3.1에서 앞 절반을 구현해 **풀 파이프라인**을 완성했다.

```
제목+주제 ─▶ OUTLINE ─▶ WRITE ─▶ [EDIT·FACT-QA] ─▶ LAYOUT ─▶ EXPORT
            (목차설계)  (집필)    (윤문/품질게이트)  (조판)    (EPUB/MD/HTML)
            └────── 신규(compose) ──────┘ └──── 기존 ebook_polisher ────┘
```

## 2. OCES 6단계 ↔ 우리 구현 매핑

| OCES 단계 | 문서 | 우리 구현 | 상태 |
|---|---|---|---|
| 1 OUTLINE | 03 §2 | `ebook_polisher/compose.py: build_outline` (규칙기반 MECE, 분량 배분) | ✅ |
| 2 WRITE | 03 §3 | `compose.py: write_book` (running-summary 캐리오버) + `llm_provider` | ✅ |
| 3 EDIT | 03 §4 | `polisher` + `consistency`(전역 통일) + `drift`(문체 봉합) | ✅ |
| 4 FACT-QA | 03 §5 | `hardfail` + `qa_report`(14+게이트, 숫자보존 blocking) | ✅(사실검증은 RAG 단계 E4) |
| 5 LAYOUT | 03 §6 | `epub_export`(제목 기준 챕터·목차 nav) | ✅ |
| 6 EXPORT | 03 §7 | `repository.export_all_formats`(md/epub/html) | ✅ (PDF/DOCX는 의존성 옵션) |

## 3. LLM Provider 추상화 (OCES 02 §2.5)

`ebook_polisher/llm_provider.py` — 모델 교체 가능한 계층.

- `StubProvider`(기본): **오프라인·결정적**. API 키 없이 전체 파이프라인 실행/테스트.
- `AnthropicProvider`: Claude 연결 스켈레톤. `ANTHROPIC_API_KEY` + `anthropic` SDK 있을 때 동작.
- 단계별 라우팅(`MODEL_ROUTING`, 03 §9): outline/edit→Opus, write→Sonnet, factqa→Sonnet.
- 키가 없으면 자동으로 결정적 생성이라, **누구나 재현 가능**하고 비용 0으로 데모된다.

## 4. 오케스트레이션 (스튜디오 API)

`apps/studio_api/service.py`:
- `compose_book(title, topic, …)` — OUTLINE→WRITE→윤문→EXPORT 풀 실행. `outline`, `manuscript_markdown`,
  `polished_markdown`, `coverage`, `qa`, `files(md/epub/html)` 반환.
- `compose_start(project_id)` — 원고가 있으면 윤문만, **없고 주제가 있으면 자동 생성→윤문**.

`apps/studio_api/main.py`:
- `POST /api/compose/book {title, topic, n_chapters, provider, mode}` — 풀 파이프라인.
- `POST /api/compose/start {project_id}` — 프로젝트 기반 실행.

## 5. 데이터 모델·잡 상태머신 (다음 단계)

OCES 02 §3·§5의 `jobs`/`outlines`/`chapters`/`events` 영속 모델과 비동기 잡 큐(Redis/Arq)·SSE 진행
스트리밍은 운영형(E4) 항목이다. 현재는 동기 오케스트레이션 + 인메모리 프로젝트 저장소로 MVP를 충족하고,
`docs/07 §10`·`oces/02`의 스키마를 그대로 승격 경로로 둔다.

## 6. 검증

- 결정적 생성(StubProvider): 동일 입력 → 동일 원고/EPUB.
- `compose_book` 엔드투엔드: 목차 N장 → 집필 → 윤문 coverage 100% → 유효 EPUB.
- 테스트: 엔진 138 + 스튜디오 10 = 148개 통과.

## 7. 원문 보관

OCES 원본 설계 문서는 [`oces/`](oces/)에 그대로 보관(00 개요·01 백서·02 아키텍처·03 알고리즘·
04 기획·05 구현가이드). 본 문서는 그 의도를 우리 코드베이스에 매핑·구현한 기록이다.
