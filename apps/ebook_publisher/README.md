# 전자책출판 독립프로그램

이 폴더는 전자책 출판만 담당하는 독립 로컬 프로그램입니다.

빠른 실행:

```powershell
powershell -ExecutionPolicy Bypass -File .\전자책출판_독립프로그램\RUN_PUBLISHER_DASHBOARD.ps1
```

브라우저 주소:

`http://127.0.0.1:8765`

이 폴더는 작성한 전자책을 국내/해외 플랫폼에 반복 등록하기 위한 운영 뼈대입니다.

핵심 원칙은 다음과 같습니다.

- 자동가입과 무인 자동등록은 각 사이트 약관, 본인인증, CAPTCHA, 세금/정산 입력 때문에 위험합니다.
- 허용되는 곳은 공식 API, 파트너 센터, CSV/엑셀 업로드, 배급사 일괄 등록을 우선 사용합니다.
- 직접 자동화가 애매한 사이트는 브라우저 자동 입력 전 단계까지 준비하고, 마지막 제출 버튼은 사람이 확인합니다.
- 원고, 표지, 소개문, 키워드, ISBN, 가격, 권리지역, AI 사용 고지, 성인/민감 콘텐츠 여부를 한 번만 입력해 사이트별 제출팩으로 변환합니다.

## 폴더 구성

- `platform_registry.csv`: 국내/해외 전자책 사이트와 자동화 가능 수준.
- `book_metadata_template.csv`: 책마다 채워 넣을 원클릭 등록용 메타데이터 양식.
- `publisher_automation_design.md`: 시스템 설계와 단계별 구축 계획.
- `scripts/generate_submission_pack.py`: 메타데이터와 사이트 목록을 읽어 사이트별 제출 체크리스트를 만듭니다.
- `out/`: 생성된 제출팩이 저장되는 폴더입니다.
- `app.py`: 로컬 웹앱 서버입니다.
- `RUN_APP.ps1`: 서버 실행기입니다.
- `RUN_PUBLISHER_DASHBOARD.ps1`: 서버 실행 후 브라우저를 여는 실행기입니다.

## 첫 실행

1. `book_metadata_template.csv`를 복사해서 실제 책 정보로 채웁니다.
2. 파일 경로는 현재 PC의 절대경로 또는 이 폴더 기준 상대경로를 넣습니다.
3. PowerShell에서 실행합니다.

```powershell
python .\전자책출판_독립프로그램\scripts\generate_submission_pack.py `
  --books .\전자책출판_독립프로그램\book_metadata.csv `
  --platforms .\전자책출판_독립프로그램\platform_registry.csv `
  --out .\전자책출판_독립프로그램\out
```

## 추천 운영 방식

처음에는 `Amazon KDP`, `Draft2Digital`, `Google Play Books`, `Kobo Writing Life`, `Apple Books`, `IngramSpark` 같은 해외 채널과 `교보문고`, `YES24`, `알라딘`, `리디` 국내 채널을 분리해 운영합니다.

국내 서점은 출판사/사업자/ISBN/거래계약이 필요한 경우가 많으므로, 자동가입보다 입점서류 자동 준비와 신청서 자동 작성 보조가 현실적입니다. 해외는 KDP와 주요 배급사를 기준으로 표준 메타데이터를 만든 뒤 확장하는 편이 안정적입니다.
