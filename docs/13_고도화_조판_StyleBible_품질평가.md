# 고도화 — 조판 프런트매터·Style Bible·품질 평가 점수

작성일: 2026-06-09

---

## 1. 추가된 것

| 영역 | 구현 | 위치 |
|---|---|---|
| 조판 프런트매터(표지·판권·목차) | `build_frontmatter` → EPUB/PDF/HTML/MD 앞에 삽입 | `ebook_polisher/frontmatter.py` |
| Style Bible(생성 일관성) | 독자/톤/말투/용어집 → 작가 프롬프트 주입 + 용어 정규화 | `ebook_polisher/style.py` |
| 품질 평가 점수(LLM-judge 대체) | 가독성·일관성·드리프트·분량 → overall 0..1 + 등급 | `ebook_polisher/evaluate.py` |

## 2. 조판 프런트매터 (OCES 03 §6 LAYOUT)

- `frontmatter.build_frontmatter(meta, chapters)`가 **표지 페이지·판권 페이지·목차**를 블록으로 생성.
- `repository.export_all_formats`가 본문 앞에 프런트매터를 덧붙여 EPUB/PDF/HTML/`polished.md` 모두에 반영.
- **coverage/QA 본문 무결성에는 영향 없음**(프런트매터는 export 전용 장식, 본문 블록 원장과 분리).
- 결과: EPUB 챕터 = 표지+판권+목차+본문장. 판권에 발행 연도·제작 크레딧·(있으면)ISBN.

## 3. Style Bible (OCES 03 §3.1/§3.3)

- `style.build_style_bible(audience, tone, honorific, glossary, length_target)` → `render_style_bible` 문자열을 작가 프롬프트(`WRITER_SYSTEM`)에 주입.
- `apply_glossary`/`glossary_violations`로 용어 표기 통일·위반 탐지(예: "리만가설"→"리만 가설").
- `service.compose_project`가 프로젝트 옵션(독자/톤/말투/용어집)으로 Style Bible을 만들어 생성에 적용.

## 4. 품질 평가 점수 (OCES 03 §10)

- `evaluate.quality_report(blocks, chapters)`:
  `overall = 0.30·일관성 + 0.20·드리프트 + 0.30·가독성 + 0.20·분량적합` → 등급 A/B/C/D.
- `qa_report`에 `evaluation` 섹션 + 게이트 18(품질 점수, report-level) 추가.
- UI 결과 패널에 **품질 등급 배지**(예: 품질 A (0.98)).

## 5. 검증

- 엔진 266(+2 skip) + 스튜디오 75 = **341 테스트 통과**.
- 엔드투엔드: compose → EPUB에 표지/판권/목차 포함(챕터 9=프런트 4+본문 5), `polished.md`에 판권·목차, QA 품질 A.

## 6. 다음 단계

- reportlab + Noto/나눔 CJK 폰트로 고품질 한글 PDF.
- 실제 이미지 모델로 표지/삽화 자동 생성, 표지 PNG에 제목 텍스트 렌더.
- 잡 중간 재개(스테이지 컨텍스트 영속화), 상호참조(앵커) 검증, LLM-as-judge(실모델) 옵션.
