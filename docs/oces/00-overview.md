# OneClick eBook Studio (OCES) — 문서 인덱스

> 본 문서 묶음은 OCES를 **다른 환경/다른 팀에서 처음부터 재구현**할 수 있도록 작성된 설계·기획 문서입니다.
> 현재 리포지토리(v0)는 FastAPI 스텁(`/health`, `/api/projects`, `/api/compose/start`)과 Next.js 기본 스캐폴드만 존재하는 초기 단계이며,
> 아래 문서들은 그 의도(제목+토픽 → 원클릭 eBook 자동 생성/조판/출간)를 온전한 제품 설계로 확장한 것입니다.

## 문서 구성

| 문서 | 내용 | 대상 독자 |
|------|------|-----------|
| [01-whitepaper.md](./01-whitepaper.md) | 기술 백서 — 문제정의, 비전, 가치제안, 차별점, 시장/리스크 | 의사결정자, 투자자, PM |
| [02-architecture.md](./02-architecture.md) | 시스템 아키텍처 — 컴포넌트, 데이터 모델, API, 인프라, 보안 | 아키텍트, 백엔드/프론트 리드 |
| [03-algorithms.md](./03-algorithms.md) | 핵심 알고리즘 — 생성 파이프라인, 오케스트레이션, 품질·일관성 제어 | ML/백엔드 엔지니어 |
| [04-product-plan.md](./04-product-plan.md) | 프로그램 기획서 — 기능명세, 사용자 흐름, 로드맵, 마일스톤, KPI | PM, 기획, 디자이너 |
| [05-implementation-guide.md](./05-implementation-guide.md) | 구현 가이드 — 스택, 폴더구조, 환경설정, 단계별 빌드 순서 | 구현 개발자 |

## 한 줄 정의

**OCES**는 사용자가 책의 *제목*과 *주제*만 입력하면, AI 오케스트레이션 파이프라인이 목차 설계 → 본문 집필 → 교정·사실검증 → 조판 → 다중 포맷(EPUB/PDF/DOCX) 출력까지 자동으로 수행하는 **"원클릭 전자책 제작 스튜디오"**다.

## 핵심 설계 원칙

1. **One-Click, but Controllable** — 기본은 완전 자동, 그러나 각 단계에서 사람이 개입(HITL)할 수 있는 체크포인트 제공.
2. **Pipeline as Orchestration** — 책 생성은 단일 LLM 호출이 아니라 단계별 에이전트의 비동기 오케스트레이션이다.
3. **Consistency First** — 긴 문서의 최대 난제는 *일관성*(용어/톤/사실/구조). 컨텍스트 압축·스타일 바이블·RAG로 보장한다.
4. **Provider-Agnostic LLM Layer** — 모델 교체 가능한 추상화 계층. 기본은 Claude(Anthropic) 최신 모델 권장.
5. **Stateless API, Stateful Job** — API는 무상태, 장시간 작업은 잡 큐 + 상태머신으로 관리.

## 현재 코드 ↔ 목표 매핑

| 현재 스텁 | 목표 |
|-----------|------|
| `POST /api/projects {title, topic}` | 프로젝트 생성 + 메타/스타일 설정 영속화 |
| `POST /api/compose/start` | 오케스트레이션 잡 enqueue, `job_id` 반환, SSE/WebSocket 진행 스트리밍 |
| `GET /health` | 헬스/레디니스 프로브 (유지) |
| (없음) | 잡 상태 조회, 산출물 다운로드, 단계별 재생성, 사용자/결제 |
