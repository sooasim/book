"""품질 평가 모듈 (Quality Evaluation — OCES 03 §10).

윤문 결과의 품질을 결정론적·자동 지표로 평가한다.
정직 봉인 철학에 따라 텍스트를 고치지 않고 점수만 산출한다.

원칙:
  - 결정론적(deterministic)·순수(pure) 함수만 둔다. 같은 입력이면 같은 출력.
  - 윤문본이 있으면 윤문본을, 없으면 원문을 본다(``block.polished_text or block.text``).
  - 산문(paragraph) 블록만 분석한다.
  - 표준 라이브러리만 사용한다.
  - 안정적 단언을 위해 모든 점수는 소수점 셋째 자리에서 반올림한다.
"""
from __future__ import annotations

import re

from ebook_polisher.consistency import consistency_report
from ebook_polisher.drift import drift_report
from ebook_polisher.models import Block

# 문장 분리: 마침표/물음표/느낌표(. ! ? 。) 경계.
_SENT_SPLIT = re.compile(r"[.!?。]+")

# 가독성 이상 문장 길이(문자 수) 구간. 40~60자를 이상으로 본다.
_IDEAL_MIN = 40.0
_IDEAL_MAX = 60.0
# 이 길이를 넘어서면 가독성 0으로 수렴한다(과도하게 긴 만연체 처벌).
_MAX_LEN = 200.0


def _split_sentences(text: str) -> list[str]:
    """텍스트를 문장 리스트로 분할한다(빈 조각 제외)."""
    if not text:
        return []
    parts = _SENT_SPLIT.split(text)
    return [p.strip() for p in parts if p and p.strip()]


def readability_score(text: str) -> float:
    """가독성 점수(0..1, 높을수록 좋음). 결정론적.

    평균 문장 길이(문자 수)를 기준으로 평가한다.
      - 이상 구간(40~60자) 안이면 1.0.
      - 그보다 짧으면 이상 최소값 대비 비례로 감점(너무 짧은 단편화).
      - 그보다 길면 이상 최대값에서 _MAX_LEN(200자)까지 선형으로 0까지 감점
        (만연체·런온 문장 처벌).

    빈 텍스트는 1.0을 반환한다(문제가 없는 것으로 본다).
    """
    sentences = _split_sentences(text)
    if not sentences:
        # 빈 텍스트: 잘못된 것이 없으므로 1.0.
        return 1.0

    avg_len = sum(len(s) for s in sentences) / len(sentences)

    if avg_len <= 0:
        return 1.0

    if _IDEAL_MIN <= avg_len <= _IDEAL_MAX:
        score = 1.0
    elif avg_len < _IDEAL_MIN:
        # 너무 짧은 문장: 이상 최소값 대비 비례. 0자→0, 40자→1.0.
        score = avg_len / _IDEAL_MIN
    else:
        # 너무 긴 문장: 60자→1.0, 200자 이상→0.0 로 선형 감소.
        span = _MAX_LEN - _IDEAL_MAX
        score = 1.0 - (avg_len - _IDEAL_MAX) / span

    # 경계 클램프.
    score = max(0.0, min(1.0, score))
    return round(score, 3)


def length_adherence(actual_words: int, target_words: int) -> float:
    """목표 분량 준수도(0..1). 결정론적.

      - 목표의 ±15% 이내면 1.0.
      - 거기서 ±100%(목표의 2배 차이) 지점까지 선형으로 0까지 감소.
      - 목표가 0 이하이면 1.0(평가 대상 아님).
    """
    if target_words <= 0:
        return 1.0

    deviation = abs(actual_words - target_words) / target_words

    if deviation <= 0.15:
        score = 1.0
    elif deviation >= 1.0:
        score = 0.0
    else:
        # 0.15 → 1.0, 1.0 → 0.0 선형 보간.
        score = 1.0 - (deviation - 0.15) / (1.0 - 0.15)

    score = max(0.0, min(1.0, score))
    return round(score, 3)


def _prose_blocks(blocks) -> list[Block]:
    return [b for b in blocks if b.block_type == "paragraph"]


def _block_text(block: Block) -> str:
    return block.polished_text or block.text


def _mean(values: list[float], default: float = 1.0) -> float:
    if not values:
        return default
    return sum(values) / len(values)


def quality_report(blocks: list, chapters: list | None = None) -> dict:
    """문서 품질 종합 리포트. 결정론적.

    항목:
      - consistency: consistency_report(blocks)["ok"]
      - drift: drift_report(blocks)["ok"]
      - readability: 산문 블록별 readability_score 평균(없으면 1.0)
      - length: chapters가 주어지면 챕터별 length_adherence 평균,
                아니면 1.0. 각 챕터 dict는 "content_md"(공백 분할로 단어 수),
                "target_words"를 가질 수 있다.

    종합(overall, 0..1) 가중합:
      0.30*consistency_ok + 0.20*drift_ok + 0.30*readability + 0.20*length

    반환: {"overall", "grade", "readability", "length",
           "consistency_ok", "drift_ok"}.
    """
    consistency = consistency_report(blocks)
    drift = drift_report(blocks)

    consistency_ok = bool(consistency["ok"])
    drift_ok = bool(drift["ok"])

    prose = _prose_blocks(blocks)
    readability = _mean(
        [readability_score(_block_text(b)) for b in prose], default=1.0
    )

    if chapters:
        length_scores = []
        for ch in chapters:
            content_md = ch.get("content_md", "") or ""
            target_words = ch.get("target_words", 0) or 0
            actual_words = len(content_md.split())
            length_scores.append(length_adherence(actual_words, target_words))
        length = _mean(length_scores, default=1.0)
    else:
        length = 1.0

    overall = (
        0.30 * (1.0 if consistency_ok else 0.0)
        + 0.20 * (1.0 if drift_ok else 0.0)
        + 0.30 * readability
        + 0.20 * length
    )
    overall = max(0.0, min(1.0, overall))

    if overall >= 0.85:
        grade = "A"
    elif overall >= 0.7:
        grade = "B"
    elif overall >= 0.5:
        grade = "C"
    else:
        grade = "D"

    return {
        "overall": round(overall, 3),
        "grade": grade,
        "readability": round(readability, 3),
        "length": round(length, 3),
        "consistency_ok": consistency_ok,
        "drift_ok": drift_ok,
    }
