# OCES 전자책 자동 채우기 — 크롬 확장 (Manifest V3)

출간 **기본정보를 한 번 저장**하면, 방문하는 어떤 출판 사이트에서도 입력칸을
**자동 인식해 채워주는** 크롬 확장. 사이트별 스크립트 없이 동작(휴리스틱 필드 인식).

## 안전 경계 (코드로 강제)
- 채우는 것: 제목·부제·저자·소개·키워드·카테고리·언어·가격·ISBN 등 **텍스트 칸**만.
- 절대 안 함: 비밀번호·캡차·인증번호·카드·계좌·주민/사업자/세금 칸(민감어 차단),
  약관 체크박스·**제출/최종 게시 버튼 클릭**(사람이 직접).
- 파일(EPUB/표지)은 브라우저 보안상 확장이 값 설정 불가 → 해당 칸을 노란색으로 표시하고
  사용자가 직접 첨부.

## 설치(개발자 모드, 로컬)
1. 크롬에서 `chrome://extensions` → 우측 상단 **개발자 모드** 켜기.
2. **압축해제된 확장 프로그램을 로드** → 이 폴더(`chrome_extension`) 선택.
3. 확장 아이콘 → **기본정보 편집**에서 한 번 입력·저장.

## 사용
1. 출판 사이트(예: 부크크, KDP, Gumroad)에서 직접 로그인.
2. 책 등록/상품 등록 폼 페이지로 이동.
3. 우측 하단 **📚 자동 채우기** 버튼(또는 팝업의 "이 페이지 자동 채우기") 클릭.
4. 채워진 칸은 초록, 직접 첨부할 파일 칸은 노랑으로 표시. 약관·인증·최종 게시는 직접.

## 구성
- `manifest.json` — MV3 (storage·activeTab·scripting, content script on `<all_urls>`)
- `field_keywords.json` — 필드 인식 키워드 + 민감어(단일 소스, `resources/field_keywords.json`와 동일)
- `src/fieldmatch.js` — 순수 인식/계획 로직(node로 테스트)
- `src/content.js` — DOM 스캔·채우기·플로팅 UI
- `src/options.*` — 기본정보 저장
- `src/popup.*` — 요약·실행 버튼

## 테스트
```bash
node tests/fieldmatch.test.js          # JS 휴리스틱 7케이스
# Python 파리티(휴리스틱 동기화): selenium_bot/tests/test_field_keywords_parity.py
```

## inspector.py / selenium_bot 과의 관계
필드 인식 규칙은 `inspector.py`(Selenium 봇)와 **동일한 단일 소스**(`field_keywords.json`)를 쓴다.
파리티 테스트가 둘의 동기화를 강제한다. 확장은 "사람이 보는 브라우저에서 즉석 자동 채움",
Selenium 봇은 "스크립트로 계획 실행·일괄 처리" 용도로 상호 보완.
