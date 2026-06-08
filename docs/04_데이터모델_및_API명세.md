# 데이터 모델 및 API 명세

작성일: 2026-06-08
문서 버전: v1.0

---

## 1. 저장 전략

- 초기: **CSV/JSON 파일** (사람이 보고 수정 가능). 구현체는 `apps/ebook_publisher`.
- 100권 초과 시: 동일 스키마로 **SQLite** 승격.
- 인코딩: `utf-8-sig`(BOM 허용, 엑셀 호환).

## 2. 표준 책 객체 (정규 모델)

CSV는 입력 편의용, 내부 처리는 아래 JSON 객체로 정규화한다.

```json
{
  "book_id": "zerozone_001",
  "title": "제로존 0=0 없음은 없다",
  "subtitle": "수학과 존재론을 잇는 대중 교양 전자책",
  "author": "ATA",
  "pen_name": "",
  "language": "ko",
  "description": "긴 소개문",
  "short_description": "짧은 소개문",
  "keywords": ["제로존", "수학", "철학", "리만가설"],
  "categories": ["Science/Mathematics", "Philosophy"],
  "files": {"manuscript": "source/manuscript.docx", "cover": "covers/front.jpg", "sample": ""},
  "build": {"epub": "build/book.epub", "pdf": "build/book.pdf"},
  "pricing": {"KRW": 12000, "USD": 9.99},
  "rights": {"territories": "world", "exclusive": false},
  "compliance": {"ai_disclosure": "ai_assisted", "adult_content": false, "copyright_owner_confirmed": true},
  "refine": {"mode": "rules", "accepted": 0, "report": "refined/report.json"}
}
```

## 3. 엔터티 스키마

### 3.1 `books` (`book_metadata.csv`)
필드는 기존 템플릿과 정합. 핵심:

| 필드 | 타입 | 설명 |
|---|---|---|
| book_id | string | 내부 고유 ID(PK) |
| title / subtitle / author / pen_name | string | 서지 |
| language | string | `ko`/`en` |
| description / short_description | text | 소개문 |
| keywords | list(`;` 구분) | 검색어 |
| categories | list(`;` 구분) | 장르 |
| age_rating | enum | general/teen/adult |
| ai_disclosure | enum | `none`/`needs_review`/`ai_assisted` |
| isbn_ebook / isbn_print | string | 식별자(선택) |
| series_name / series_number | string/number | 시리즈 |
| price_krw / price_usd | number | 가격 |
| rights_territories | string | `world`/국가코드 |
| manuscript_path / cover_path / sample_path | path | 파일 |
| format | enum | docx/md/epub/pdf |
| kdp_select | bool | 독점 여부 |
| notes | text | 비고 |

### 3.2 `platforms` (`platform_registry.csv`)
| 필드 | 타입 | 설명 |
|---|---|---|
| platform_id | string | PK |
| region | enum | `kr`/`global` |
| platform_name | string | 표시명 |
| entry_type | enum | self_publish/aggregator/retailer_partner/direct_store |
| primary_url | url | 진입 URL |
| automation_level | enum | assisted_browser/aggregator/manual_contract/direct_store |
| preferred_route | text | 권장 경로 |
| notes | text | 주의점 |

### 3.3 `publication_status` (`publication_status.csv`)
| 필드 | 타입 | 설명 |
|---|---|---|
| book_id, platform_id | string | 복합 키 |
| status | enum | not_started/prepared/blocked/input_ready/human_review/submitted/approved/live/rejected/paused |
| last_action | text | 마지막 작업 |
| platform_url / admin_url | url | 판매/관리 |
| reviewer_note | text | 심사 메모 |
| next_action | text | 다음 행동 |
| updated_at | datetime | 갱신 |

### 3.4 `publisher_accounts` (템플릿, 민감 → 미커밋)
| 필드 | 타입 | 설명 |
|---|---|---|
| platform_id | string | FK |
| account_status | enum | not_created/created/verified/tax_ready/payment_ready/blocked |
| login_hint | string | 힌트만(비밀번호 금지) |
| tax_ready / payment_ready | bool | 준비 여부만 |
| contract_status | enum | none/requested/reviewing/signed |

### 3.5 윤문 산출 (`refined/*.json`)
`02 윤문기 설계서` 2장 참조 — `report.json`, `meta_candidates.json`, `readability.json`.

## 4. 식별자·상태 열거형

- `ai_disclosure`: `none`(AI 미사용) · `needs_review`(미검토) · `ai_assisted`(보정 사용 고지).
- `severity`(윤문 제안): `auto` · `review` · `manual`.
- `suggestion.status`: `pending` · `accepted` · `rejected`.

## 5. REST API 명세

로컬 앱(`127.0.0.1:8765`) 기준. 기존 엔드포인트 + 신규(윤문/변환/검수).

### 5.1 기존(구현됨)
| 메서드 | 경로 | 기능 |
|---|---|---|
| GET | `/api/state` | 전체 상태(요약/책/플랫폼/매트릭스) |
| POST | `/api/generate-packs` | 제출팩 생성 |
| POST | `/api/check-toolchain` | 도구 점검 |
| POST | `/api/books` | 책 추가/수정 |
| POST | `/api/status` | 상태 갱신 |
| GET | `/api/assist-command` | 반매크로 실행 명령 생성 |

### 5.2 신규(설계)
| 메서드 | 경로 | 기능 | 요청 본문(요약) |
|---|---|---|---|
| POST | `/api/refine/{book_id}` | 윤문 실행 | `{mode, style_profile, glossary}` |
| GET | `/api/refine/{book_id}/report` | 제안 리포트 | — |
| POST | `/api/refine/{book_id}/apply` | 제안 반영 | `{accept:[ids], reject:[ids]}` |
| GET | `/api/refine/{book_id}/meta` | 메타 후보 | — |
| POST | `/api/build/{book_id}` | EPUB/PDF 변환 | `{formats:["epub","pdf"]}` |
| POST | `/api/review/{book_id}` | 검수 실행 | — |
| GET | `/api/review/{book_id}` | 검수 결과 | — |
| POST | `/api/orchestrate/{book_id}` | 원클릭 단계 실행 | `{from:"refine", to:"packs"}` |

### 5.3 응답 공통 형식
```json
{ "ok": true, "data": { }, "warnings": [], "errors": [] }
```

### 5.4 에러 코드
| code | 의미 | 사용자 메시지 |
|---|---|---|
| `missing_manuscript` | 원고 없음 | 원고 파일 경로가 없습니다 |
| `missing_cover` | 표지 없음 | 표지 파일 경로가 없습니다 |
| `missing_required_metadata` | 필수 누락 | 제목/저자/소개문/가격 확인 |
| `epubcheck_failed` | EPUB 표준 실패 | 변환본 오류를 수정하세요 |
| `exclusive_conflict` | 독점 충돌 | KDP Select 충돌 확인 |
| `human_gate_required` | 사람 승인 필요 | 약관/인증/최종 제출은 직접 |

## 6. 파일 시스템 계약

```text
projects/{book_id}/
  source/      # 원문(.gitignore)
  refined/     # 윤문 산출(report.json, refined.md, meta_candidates.json)
  build/       # EPUB/PDF(.gitignore)
  review/      # 검수 리포트
out/{book_id}/ # 플랫폼별 제출팩(공유 산출)
book_metadata.csv / platform_registry.csv / publication_status.csv
```

## 7. 마이그레이션 노트 (CSV→SQLite)

- 테이블은 위 엔터티 1:1. PK/복합키 동일.
- list 필드(`keywords`,`categories`)는 조인 테이블 또는 JSON 컬럼.
- 마이그레이션 스크립트는 CSV를 단일 진실원으로 export/import 왕복 가능해야 한다.
