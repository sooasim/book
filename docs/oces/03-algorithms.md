# OneClick eBook Studio — 핵심 알고리즘 (Algorithms)

문서 버전: 1.0 · 상태: Draft

> 본 문서는 "제목+주제 → 완성 eBook"을 만드는 **오케스트레이션 파이프라인**과 각 단계의 알고리즘,
> 그리고 가장 어려운 문제인 **장문 일관성·품질 제어**를 다룬다. 의사코드는 언어 중립적으로 표기한다.

---

## 1. 전체 파이프라인 (Pipeline Overview)

```
입력: { title, topic, audience, tone, language, length_target, sources? }

1) OUTLINE   주제 → 장/절 트리 + 챕터별 집필 브리프
2) WRITE     챕터 루프: 브리프 + 캐리오버 컨텍스트 + RAG → 본문 초안
3) EDIT      전역 교정: 톤/용어/구조/전환부 통일, 중복 제거
4) FACT-QA   사실검증·표절·가독성·금칙어 게이트
5) LAYOUT    Markdown SSOT → 조판 구조(목차/각주/이미지 슬롯)
6) EXPORT    멀티 렌더: EPUB / PDF / DOCX / HTML

출력: artifacts[] + 품질 리포트
```

각 단계는 **상태머신의 전이**이며, 게이트 통과 실패 시 재생성 또는 사람 개입(HITL)으로 분기.

---

## 2. 단계 1 — Outline (목차 설계)

### 목적
주제를 **MECE(상호배타·전체포괄)**한 장/절 트리로 분해하고, 각 챕터에 *집필 브리프*(무엇을/왜/어떤 순서로)를 부여.

### 알고리즘
```
function build_outline(project):
    plan = LLM.complete(
        system = OUTLINE_SYSTEM_PROMPT(audience, tone, language),
        user   = f"제목:{title}\n주제:{topic}\n목표분량:{length_target}단어",
        schema = OutlineSchema   # 구조화 출력(JSON) 강제
    )
    validate_mece(plan)                  # 중복/누락 휴리스틱 점검
    allocate_word_budget(plan, length_target)   # 챕터별 분량 배분
    for ch in plan.chapters:
        ch.brief = derive_brief(ch)      # 핵심 포인트/예시/피해야 할 것
    return plan
```

### 분량 배분 (Word Budget Allocation)
- 전체 목표 `L`을 챕터 중요도 가중치 `w_i`에 비례 배분: `len_i = L * w_i / Σw`.
- 너무 작은 절은 병합, 너무 큰 절은 분할(목표 ±20% 범위로 정규화).

### 품질 휴리스틱
- 장 수 적정성(예: 6~15장), 절 깊이 ≤ 3, 제목 중복 임베딩 유사도 < 0.85.

---

## 3. 단계 2 — Write (본문 집필) — **핵심 일관성 엔진**

긴 글은 컨텍스트 윈도우를 초과한다. 따라서 **챕터 단위 생성 + 컨텍스트 캐리오버**로 일관성을 유지한다.

### 3.1 컨텍스트 구성 (각 챕터 i 집필 시)
주입 컨텍스트 = 다음의 합:
```
[전역 불변]  Style Bible(용어집/톤/페르소나/금칙어), 책 한줄 요지, 전체 목차
[직전 맥락]  이전 챕터들의 압축 요약(running summary)  ← 토큰 절약 핵심
[로컬]       현재 챕터 브리프 + 인접(i-1, i+1) 절 제목
[근거]       RAG 검색 결과 top-k (사용자 자료/사실 고정)
```

### 3.2 의사코드
```
function write_book(project, outline):
    style = project.style_bible
    running_summary = ""            # 누적 압축 컨텍스트
    for i, ch in enumerate(outline.chapters):
        evidence = RAG.search(query=ch.brief, k=K) if sources else []
        ctx = build_context(style, book_thesis, outline,
                            running_summary, ch.brief, evidence)
        draft = LLM.complete(WRITER_SYSTEM, ctx, target_words=ch.len)
        draft = enforce_local_rules(draft, style)   # 용어 치환/금칙어
        ch.content_md = draft
        ch.summary   = summarize(draft, max_tokens=S)   # 다음 챕터로 캐리오버
        running_summary = compress(running_summary + ch.summary)  # 윈도우 유지
        checkpoint(job, stage="write", chapter=i)
    return outline.chapters
```

### 3.3 일관성 보장 기법 (Consistency Techniques)
1. **Style Bible 주입**: 용어집(canonical terms), 톤, 1인칭/2인칭, 단위/표기 규칙을 모든 챕터에 고정.
2. **Running Summary 압축**: 이전 챕터 전체가 아니라 *요약*을 캐리오버 → 토큰 선형 증가 방지.
3. **용어 정규화 패스**: 생성 후 용어집 기준 치환(예: "AI"↔"인공지능" 혼용 제거).
4. **앵커 참조**: "앞서 N장에서 다룬 …" 같은 상호참조를 목차 인덱스로 검증.
5. **병렬 집필 + 사후 봉합**: 속도 위해 챕터 병렬 생성 시, EDIT 단계에서 전환부(transition)를 재작성해 봉합.

### 3.4 RAG (근거 고정으로 환각 억제)
```
function rag_search(query, project):
    q = embed(query)
    hits = vector_store.knn(q, filter=project_id, k=K)
    return rerank(hits, query)        # 교차 인코더/LLM 리랭크(옵션)
```
- 사실 주장 문장에는 근거 인용(`[source_id]`)을 달도록 프롬프트로 강제 → FACT-QA에서 검증.

---

## 4. 단계 3 — Edit (전역 교정)

### 목적
챕터 단위 생성으로 생긴 **경계 불연속**(톤 점프, 중복 설명, 전환부 단절)을 전역 관점에서 봉합.

### 알고리즘
```
function global_edit(chapters, style):
    # (a) 슬라이딩 윈도우로 인접 챕터 전환부 매끄럽게
    for i in 1..n-1:
        boundary = tail(chapters[i-1]) + head(chapters[i])
        rewritten = LLM.complete(EDIT_TRANSITION, boundary, style)
        apply(rewritten)
    # (b) 중복 탐지: 문단 임베딩 유사도 > θ → 병합/삭제 제안
    dedup(chapters, threshold=0.9)
    # (c) 톤/용어 전역 통일 패스
    normalize_tone_terms(chapters, style)
    return chapters
```

### 가독성 개선
- 문장 길이 분포, 수동태 비율, 전문용어 밀도 측정 → 목표 독자 수준에 맞게 리라이트.

---

## 5. 단계 4 — Fact-QA (품질 게이트)

**모든 검사를 통과해야** 다음 단계로 진행하는 **게이트**. 실패 항목은 해당 챕터 재생성 또는 HITL.

### 검사 항목
```
checks = {
  factuality:  근거 없는 사실 주장 탐지 → RAG 재확인 / 인용 요구
  plagiarism:  임베딩 유사도 + 외부 표절 API → 임계 초과 시 리라이트
  readability: 가독성 지수(예: 한국어 적합 지표) 목표 범위
  banned:      금칙어/민감표현/정책 위반 필터
  structure:   목차 ↔ 본문 정합(누락 절/순서)
  consistency: 용어집 위반/상호참조 깨짐
}
```

### 게이트 로직
```
function quality_gate(chapter):
    report = run_checks(chapter)
    if report.all_pass(thresholds):
        chapter.status = "approved"
    elif report.retryable and chapter.retries < MAX:
        regenerate_with_feedback(chapter, report.failures)   # 자동 수정 루프
    else:
        flag_for_human(chapter, report)                      # HITL
    return report
```

### 자동 수정 루프 (Self-Refine)
- 실패 사유를 구조화해 프롬프트에 피드백 → 재생성 → 재검사. 최대 N회. 수렴 실패 시 사람에게.

---

## 6. 단계 5 — Layout (조판)

### 목적
Markdown 단일 소스(SSOT)를 **렌더 가능한 구조**로 변환: 목차(ToC), 각주, 그림/표 슬롯, 페이지 메타.

### 알고리즘
```
function layout(book_md, project):
    ast = markdown_to_ast(book_md)
    toc = build_toc(ast, max_depth=3)
    resolve_cross_refs(ast)              # "3장 참조" → 앵커 링크
    place_media(ast)                     # 이미지/표 캡션·번호
    inject_frontmatter(ast, project)     # 표지/판권/머리말
    return LayoutModel(ast, toc, metadata)
```
- (옵션) **이미지 생성**: 챕터 핵심 개념 → 이미지 프롬프트 → 표지/삽화 생성 후 슬롯 배치.

---

## 7. 단계 6 — Export (멀티 포맷 렌더)

단일 LayoutModel → 다중 포맷. 변환기 권장:
```
Markdown/HTML  : 자체 렌더러
EPUB           : pandoc 또는 ebooklib
PDF            : HTML→PDF (WeasyPrint/Prince) 또는 pandoc+LaTeX
DOCX           : pandoc
```
```
function export(layout, formats):
    artifacts = []
    for fmt in formats:
        bytes = RENDERERS[fmt].render(layout)
        uri = object_store.put(project_id, fmt, bytes)
        artifacts.append(Artifact(fmt, uri, len(bytes)))
    return artifacts
```

---

## 8. 오케스트레이터 (Orchestrator)

```
function orchestrate(job):
    project = load(job.project_id)
    stages = [outline, write, edit, factqa, layout, export]
    start = resume_point(job.checkpoint)        # 크래시 복구
    for stage in stages[start:]:
        emit(job, "stage_started", stage)
        try:
            result = stage.run(project, budget=token_guard(job))
        except Retryable as e:
            if stage.retries < MAX: retry(); continue
            else: fail(job, e); return
        if stage.needs_review(result):
            pause(job); return                  # HITL → 외부 resume 대기
        checkpoint(job, stage, result)
        emit(job, "stage_done", stage)
    emit(job, "job_done", artifacts)
```

### 핵심 속성
- **멱등성**: 단계 키 `job_id:stage[:chapter]`로 중복 방지.
- **체크포인트**: 매 전이마다 상태 스냅샷 저장 → 재개 가능.
- **토큰 가드**: 누적 토큰이 예산 초과 시 단계 다운시프트(모델 티어↓) 또는 일시정지.

---

## 9. LLM 라우팅 / 비용 최적화

```
정책(예):
  outline  → 고품질 모델(구조적 추론 중요)
  write    → 중급 모델(분량 많음, 비용 민감) + 캐싱
  edit     → 고품질 모델(전역 일관성)
  factqa   → 중급 + 검사 도구(임베딩/외부 API)
  layout/export → 비-LLM(결정적 변환)
```
- **프롬프트 캐싱**: 변하지 않는 시스템/Style Bible 부분 캐시.
- **폴백**: 1차 모델 실패/타임아웃 → 대체 모델 라우팅.
- **권장 기본 모델**: 장문 일관성·지시준수가 중요한 outline/edit에는 Anthropic Claude 최신 모델 권장. Provider 추상화로 교체 가능.

---

## 10. 평가 (Evaluation)

- **자동 지표**: 일관성 점수(용어집 위반율·상호참조 정합), 가독성, 중복률, 근거 인용률.
- **LLM-as-judge**: 루브릭(정확성/유용성/구성/톤) 기반 채점. 단, 판정 편향 보정·샘플 검수 병행.
- **회귀 테스트**: 고정 주제 셋으로 파이프라인 변경 시 품질 회귀 감지.
- **휴먼 평가**: 검수 후 출판률, 수정량(편집 거리)으로 실효 품질 추적.

---

## 부록 A — 핵심 프롬프트 슬롯(스켈레톤)

```
OUTLINE_SYSTEM:  "너는 {audience}를 위한 {topic} 분야 편집장이다. MECE한 목차를
                  JSON 스키마로 설계하라. 각 챕터에 집필 브리프를 포함하라."
WRITER_SYSTEM:   "Style Bible을 절대 준수. 근거 없는 사실 주장 금지(인용 [src] 사용).
                  이전 요약과 모순 금지. 목표 분량 ±15%."
EDIT_TRANSITION: "두 챕터 경계의 전환을 자연스럽게. 중복 제거. 톤/용어 통일."
FACTQA_SYSTEM:   "각 사실 주장에 대해 근거 유무·정확성을 판정하고, 위반을 구조화해 보고."
```
> 실제 프롬프트는 모델/언어별로 튜닝하고, Style Bible과 스키마는 외부 설정으로 분리한다.
