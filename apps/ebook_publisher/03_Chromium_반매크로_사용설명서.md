# Chromium 반매크로 사용설명서

## 1. 목적

이 프로그램은 별도 Chromium 브라우저를 띄운 뒤 사용자가 직접 로그인한 페이지를 인식하고, 전자책 기본정보를 입력칸에 자동으로 넣어주는 반매크로 도구입니다.

처음에는 페이지 구조를 학습합니다. 다음부터는 저장된 매핑을 사용해서 같은 플랫폼의 글등록/책등록 화면을 더 빠르게 채웁니다.

## 2. 안전 경계

자동으로 하지 않는 것:

- 회원가입 최종 완료
- 로그인 비밀번호 입력
- CAPTCHA 우회
- 본인인증 우회
- 약관 동의 체크
- KDP Select 같은 독점 계약 선택
- 최종 출판/제출 버튼 클릭
- 세금번호/계좌번호 저장

자동으로 하는 것:

- 제목 입력
- 부제 입력
- 저자명 입력
- 소개문 입력
- 키워드 입력
- 카테고리 후보 입력
- 가격 입력
- ISBN 입력
- 원고/표지 파일 업로드 보조
- 페이지 입력칸 인식
- 다음 실행을 위한 입력칸 매핑 저장

## 3. 파일 구성

- `scripts/semi_macro_browser.py`: 반매크로 본체
- `scripts/run_kdp_assist.ps1`: KDP 샘플 실행기
- `publisher_profile_template.csv`: 출판자 기본정보 템플릿
- `book_metadata_template.csv`: 책 기본정보 템플릿
- `mappings/`: 사이트별 학습 매핑 저장 폴더
- `.chromium_profile/`: 별도 Chromium 로그인 세션 저장 폴더

## 4. 첫 실행 절차

PowerShell에서 실행합니다.

```powershell
python .\전자책_출판자동화\scripts\semi_macro_browser.py `
  --platform amazon_kdp `
  --book-id zerozone_001 `
  --mode assist
```

또는 샘플 실행기를 씁니다.

```powershell
.\전자책_출판자동화\scripts\run_kdp_assist.ps1
```

## 5. 화면에서 해야 할 일

1. 별도 Chromium 창이 열립니다.
2. 사이트에 직접 로그인합니다.
3. 본인인증이나 CAPTCHA가 나오면 직접 처리합니다.
4. 책 등록 페이지까지 직접 이동합니다.
5. PowerShell 창으로 돌아와 Enter를 누릅니다.
6. 프로그램이 페이지의 입력칸을 스캔합니다.
7. 제목/저자/소개문/가격 같은 칸을 자동으로 채웁니다.
8. 매핑이 `mappings/{platform_id}.json`에 저장됩니다.
9. 최종 제출은 직접 확인하고 누릅니다.

## 6. 모드 설명

| 모드 | 명령 | 설명 |
|---|---|---|
| 검사만 | `--mode inspect` | 입력칸을 인식하지만 값은 넣지 않음 |
| 학습 | `--mode learn` | 페이지를 인식해서 자동 입력하고 매핑 저장 |
| 보조 | `--mode assist` | 저장된 매핑과 새 페이지 인식을 같이 사용 |
| 원클릭 입력 | `--mode one-click` | 저장된 매핑만 사용해서 빠르게 입력 |

## 7. 다음부터 원클릭에 가깝게 쓰는 법

첫 실행에서 매핑이 저장된 뒤에는 이렇게 실행합니다.

```powershell
python .\전자책_출판자동화\scripts\semi_macro_browser.py `
  --platform amazon_kdp `
  --book-id zerozone_001 `
  --mode one-click
```

단, 사이트 화면 구조가 바뀌면 `assist` 모드로 다시 학습해야 합니다.

## 8. 플랫폼 추가 방법

`platform_registry.csv`에 새 줄을 추가합니다.

```csv
platform_id,region,platform_name,entry_type,primary_url,automation_level,preferred_route,notes
my_platform,global,My Platform,self_publish,https://example.com/,assisted_browser,Login then go to book form,Final submit by user
```

그 다음 실행합니다.

```powershell
python .\전자책_출판자동화\scripts\semi_macro_browser.py `
  --platform my_platform `
  --book-id zerozone_001 `
  --mode assist
```

## 9. 책 정보 바꾸는 법

`book_metadata_template.csv`를 복사해서 실제 책 정보 CSV를 만듭니다.

예:

```powershell
Copy-Item .\전자책_출판자동화\book_metadata_template.csv .\전자책_출판자동화\my_books.csv
```

실행 시 `--books`로 지정합니다.

```powershell
python .\전자책_출판자동화\scripts\semi_macro_browser.py `
  --platform amazon_kdp `
  --book-id zerozone_001 `
  --books .\전자책_출판자동화\my_books.csv `
  --mode assist
```

## 10. 출판자 정보 바꾸는 법

`publisher_profile_template.csv`를 복사해서 개인용 프로필 CSV를 만들고 값을 채웁니다. 세금번호, 계좌번호, 비밀번호는 넣지 마세요.

```powershell
Copy-Item .\전자책_출판자동화\publisher_profile_template.csv .\전자책_출판자동화\my_publisher_profile.csv
```

실행 시 `--profile`로 지정합니다.

```powershell
python .\전자책_출판자동화\scripts\semi_macro_browser.py `
  --platform amazon_kdp `
  --book-id zerozone_001 `
  --profile .\전자책_출판자동화\my_publisher_profile.csv `
  --mode assist
```

## 11. 문제 해결

입력이 잘못 들어갔을 때:

- 브라우저에서 직접 지웁니다.
- `--mode inspect`로 어떤 칸을 어떻게 인식하는지 확인합니다.
- `mappings/{platform_id}.json`을 삭제하고 다시 학습합니다.

파일 업로드가 실패할 때:

- `book_metadata_template.csv`의 `manuscript_path`, `cover_path`가 실제 파일인지 확인합니다.
- 상대경로는 `C:\Users\ATA\Documents\총정리` 기준으로 해석됩니다.

사이트가 바뀌었을 때:

- 기존 매핑이 틀릴 수 있습니다.
- `--mode assist`로 다시 학습합니다.

## 12. 실제 개발 확장 순서

1. KDP에서 첫 페이지 자동 입력을 안정화합니다.
2. Draft2Digital을 추가합니다.
3. Gumroad/Payhip 같은 직접판매 플랫폼을 추가합니다.
4. 국내 플랫폼은 신청서 자동 작성과 브라우저 입력 보조로 분리합니다.
5. UI 대시보드에서 `입력 보조 시작` 버튼으로 이 스크립트를 호출하게 만듭니다.
