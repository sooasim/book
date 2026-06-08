# 윤문 체크리스트 600 (필수 자산)

이 폴더는 윤문기(Refiner)가 **반드시 전수 적용**해야 하는 출판용 AI 원고 윤문·교정·교열 체크리스트다.

| 파일 | 역할 |
|---|---|
| `윤문교정_체크리스트_600.md` | **단일 진실원(원본)**. 사람이 읽고 편집하는 정본. |
| `checklist_600.json` | 엔진 소비용. `build_checklist.py`로 원본에서 생성(재현 가능). |

## 재생성

```bash
python3 apps/ebook_publisher/scripts/build_checklist.py
# -> resources/checklist/checklist_600.json (총 600항목)
```

## 강제 규칙 (Hard Gate)

- 모든 윤문 실행은 600항목 각각에 상태(`pass`/`fail`/`na`/`waived`/`pending`)를 기록한 `checklist_run.json`을 만든다.
- `pending>0` 또는 `fail>0`이면 **변환·검수·출판이 차단**된다(`ComplianceGate.checklist_incomplete`).
- `na`/`waived`는 사유를 반드시 남긴다(감사 추적).

## 라우팅 분류(suggested_method)

| 방법 | 항목 수 | 의미 |
|---|---:|---|
| `rules` | 114 | 규칙엔진 (반)자동 점검 |
| `llm_review` | 82 | LLM 보조 문맥 검토 |
| `human_review` | 352 | 사람 최종 판단 |
| `policy` | 52 | 컴플라이언스·법무·AI 고지·표절률 |

설계 상세: [`../../docs/02_윤문기엔진_상세설계서.md`](../../docs/02_윤문기엔진_상세설계서.md) §1.1.
