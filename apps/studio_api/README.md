# OneClick eBook Studio — API

`sooasim/oneclick-ebook-studio` v0 스켈레톤을 계승하여, 더미 TODO 엔드포인트를
우리 실제 엔진(`apps/ebook_polisher`)에 배선한 FastAPI 서비스.

## 구조

- `service.py` — 비즈니스 로직(프레임워크 비의존). 엔진 파이프라인 호출. **테스트 대상**.
- `main.py` — FastAPI HTTP 바인딩 + CORS(웹 프론트 연결).
- `requirements.txt` / `Dockerfile` / `.tool-versions` — 원본 스튜디오 설정 계승.

## 엔드포인트

| 메서드 | 경로 | 기능 |
|---|---|---|
| GET | `/health` | 상태 + 엔진 표기 |
| POST | `/api/projects` | 프로젝트 생성(title/topic/genre/author) |
| GET | `/api/projects` | 목록 |
| GET | `/api/projects/{id}` | 단건 |
| POST | `/api/polish` | **원고 텍스트 → 실제 윤문**(coverage/QA/결과 반환) |
| POST | `/api/compose/start` | 프로젝트 오케스트레이션(윤문 실행·결과 저장) |

## 실행

```bash
cd apps/studio_api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# http://127.0.0.1:8000/docs
```

## 테스트 (FastAPI 불필요 — service 계층 직접)

```bash
cd apps/studio_api
python3 -m unittest tests.test_service -v   # 7 tests
```

## 엔진 배선

`service.py`가 `apps/ebook_polisher`를 import 경로에 추가하고
`ebook_polisher.cli.build_pipeline(mode, ":memory:", out)`로 파이프라인을 실행한다.
즉, `/api/polish`는 page/block 원장·Coverage Gate·무손실 보존·QA 14게이트를 그대로 통과한 결과를 반환한다.
