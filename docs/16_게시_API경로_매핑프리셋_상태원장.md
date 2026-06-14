# 게시 고도화 — 공식 API 경로 · 입력칸 매핑 프리셋 · 결과 상태 원장

작성일: 2026-06-14
구현체: `apps/ebook_publisher/selenium_bot/` (api/, mappings/, status_ledger.py)

---

## 1. 추가된 것

| 영역 | 구현 | 비고 |
|---|---|---|
| 공식 API 경로(레벨 4) | `selenium_bot/api/` (base·gumroad·leanpub·publishdrive·factory) | 약관 친화적. 토큰/requests 없으면 dry-run·가드 |
| 입력칸 매핑 프리셋 | `selenium_bot/mappings/{platform}.json` 7종 | KDP·부크크·Gumroad·Payhip·Leanpub·Kobo·Google |
| 게시 결과 상태 원장 | `selenium_bot/status_ledger.py` → `publish_results.csv` | 판매 URL/심사 상태 누적(upsert) |
| CLI | `api-list` · `api-publish` · `status` | dry-run 기본, `--live` 시 실제 호출 |

## 2. 공식 API 경로 (ToS 친화적, 우선 사용 권장)

브라우저 자동화보다 **공식 API가 있으면 그 경로를 우선**한다(약관 위반·계정정지 위험 최소).

- `api/base.py: ApiConnector`
  - `build_payload(book, files)` / `dry_run(...)` — **네트워크 없이** 결정적 페이로드 생성(테스트 가능).
  - `publish(...)` — 유일한 네트워크 메서드. 가드 순서: 토큰 없음→`missing_token`,
    requests 미설치→`requests_not_installed`, 예외→`network_error`. (토큰은 환경변수)
  - 책임 고지(`human_review_note`): API 경유여도 가격·세금·권리·AI 고지는 발행자 책임.
- 커넥터: **Gumroad**(`GUMROAD_ACCESS_TOKEN`, 가격→센트), **Leanpub**(`LEANPUB_API_KEY`),
  **PublishDrive**(`PUBLISHDRIVE_API_KEY`). `factory.get_connector/has_api/api_platform_ids`.

```bash
python -m selenium_bot.cli api-list
python -m selenium_bot.cli api-publish --platform gumroad --book-json book.json --epub OUT/book.epub   # dry-run
GUMROAD_ACCESS_TOKEN=... python -m selenium_bot.cli api-publish --platform gumroad --book-json book.json --live
```

## 3. 입력칸 매핑 프리셋

`assist`가 바로 폼을 채울 수 있도록 주요 7개 플랫폼의 출발 셀렉터를 동봉.
실제 사이트 구조 변경에 대비해 `inspect`로 보정·누적 학습한다(프리셋 → 학습으로 덮어씀).

## 4. 게시 결과 상태 원장

`status_ledger.record(book_id, platform_id, status, method=, platform_url=, ...)` → `publish_results.csv`(upsert).
상태값: prepared·submitted·in_review·live·rejected·paused·failed. `status` CLI로 요약/목록 확인.
api-publish 는 결과를 자동으로 원장에 기록한다.

## 5. 권장 라우팅

1) **API 지원**(Gumroad/Leanpub/PublishDrive 등) → `api-publish`(레벨 4).
2) **assisted_browser**(KDP/Kobo/Google/부크크 등) → `assist`(폼 자동 채움 + 업로드, 최종 게시는 사람).
3) **manual_contract**(국내 대형서점/일본 리테일러 등) → 입점 서류·신청서 준비(자료 자동 생성).

## 6. 안전 경계(불변)

API/브라우저 어느 경로든 회원가입 최종·CAPTCHA·본인인증·약관·독점·세금/정산·최종 게시는 사람.
`gates.py`와 어시스턴트 분기, API 토큰 가드로 코드 레벨에서 강제.

## 7. 검증

- selenium/requests 미설치 환경에서 **selenium_bot 148 테스트 통과**(엔진 288·스튜디오 78 영향 없음).
- 엔드투엔드 데모: 전자책 생성 → 게시 계획 → 어시스턴트 폼 채움·EPUB 업로드 → **최종 게시에서 정지**;
  API dry-run 페이로드 생성·`--live` 토큰 가드·상태 원장 기록 확인.
