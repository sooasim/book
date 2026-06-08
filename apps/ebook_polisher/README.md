# Ebook Polisher (Ink&Press v3 엔진)

원장(Ledger) 기반 무손실 전자책 윤문 엔진. 3000페이지 이상 장편도 **누락 0**을 목표로
페이지·블록 단위로 처리한다. 설계 근거: [`../../docs/07_아키텍처v3_원장기반무손실엔진_통합백서.md`](../../docs/07_아키텍처v3_원장기반무손실엔진_통합백서.md).

## 핵심 원칙

- 페이지/블록 = **책임 단위**, 청크 = **작업 단위**.
- AI 출력은 `block_id`를 보존하는 **계약**(자유 문장 금지).
- **Coverage Gate**: `source = parsed = polished = assembled` 페이지 수 일치해야 출력.
- 코어(E1)는 **외부 의존성 없이**(표준 라이브러리만) 결정적으로 동작.

## 빠른 실행

```bash
cd apps/ebook_polisher
python3 -m ebook_polisher.cli INPUT.md --out OUTDIR            # 규칙 기반(결정적)
python3 -m ebook_polisher.cli INPUT.md --out OUTDIR --mode agency   # 7-Agency 토론
python3 -m ebook_polisher.cli INPUT.md --out OUTDIR --db polish.db  # 재개용 영속 DB
```

## 테스트

```bash
cd apps/ebook_polisher
python3 -m unittest discover -s tests -p 'test_*.py' -v   # 76 tests
```

## 모듈 지도

| 파일 | 책임 | 단계 |
|---|---|---|
| `models.py` | 고정 계약: Block/Page/Chunk/StyleProfile/PolishedBlock/AuditEvent/Memory + Protocol | E1 |
| `normalizer.py` | 유니코드 NFC·공백·비가시문자 정규화(멱등) | E1 |
| `parser.py` | TXT/MD → Page/Block 원장(안정적 id) | E1 |
| `chunker.py` | Ledger-aware 청킹 + Adaptive Boundary Score | E1 |
| `verifier.py` | 청크/블록 coverage, 의미 보존, 금지 변경 검사 | E1 |
| `coverage_gate.py` | 단계별 페이지 수 일치 강제 게이트 | E1 |
| `repository.py` | SQLite 원장 + 세 겹 컨텍스트 페이로드 + 감사 | E1 |
| `polisher.py` | RulesPolisher(결정적 무손실, block_id 보존) | E1 |
| `hardfail.py` | 금지어·괄호·마크다운·빈청크 Hard-Fail 게이트 | E1 |
| `pipeline.py` | parse→chunk→polish→verify→gate→export(재개 가능) | E1 |
| `export.py` | Markdown(코어) + DOCX/EPUB(선택) | E1 |
| `cli.py` | 원클릭 진입점 | E1 |
| `agents.py` | 7-Agency 토론(정직 봉인 ★/◑) | E3 기반 |
| `scheduler.py` | CID 의존성 DAG 병렬 스케줄러 | E3 기반 |
| `memory.py` | 전역 기억 라우터(가중 점수) | E2/E3 기반 |
| `prompts.py` | 프롬프트 + Prompt Gene 선택 | E3 기반 |
| `style_bible.py` | Style Profile 생성/렌더 | E2 기반 |

## 보장(현재 사이클, E1)

- page/block coverage 100%, 누락 0 (테스트로 강제).
- 숫자/ISBN/URL/고유명사 무손실 보존.
- `rules` 모드 결정성(동일 입력 → 동일 출력).
- 중단→재개 시 멱등(이미 처리한 청크 건너뜀).

## 다음 단계 (로드맵 docs/07 §13)

- E2: Structure Tree, Style Bible 자동화, 전역 메모리, Consistency Pass, DOCX/EPUB 입력.
- E3: 7-Agency LLM 토론, CID 병렬 실제 연결, 정직 봉인 결재 UI, Hard-Fail 차단·재시도 루프.
- E4: Batch API, Qdrant, OpenTelemetry, 비용 예측.
