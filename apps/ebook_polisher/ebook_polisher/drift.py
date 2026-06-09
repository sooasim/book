"""Style Drift Detector (docs/07 §9).

원고 전체에서 한 블록만 문체가 튀는 '문체 이탈(style drift)'을 감지한다.
산문(paragraph) 블록의 평균 문장 길이를 표본으로 z-score 이상치를 찾는다.

원칙:
  - 결정론적(deterministic)·순수(pure) 함수만 둔다. 같은 입력이면 같은 출력.
  - 윤문본이 있으면 윤문본을, 없으면 원문을 본다(``block.polished_text or block.text``).
  - paragraph 블록만 분석한다.
"""
from __future__ import annotations

import re
import statistics

from ebook_polisher.models import Block

# 문장 종결 위치: 마침표/물음표/느낌표 또는 한국어 종결 어미가
# 공백 또는 문자열 끝 앞에 올 때 분리한다.
#   - 라틴/한자 종결부호: . ! ? 。
#   - 한국어 종결 어미(고정밀형): 다 까 요 죠 네 군
#     ('라/자/지' 등은 문장 중간 연결어로도 흔히 쓰여 오분할을 유발하므로 제외)
_KO_ENDERS = "다까요죠네군"
_SPLIT_RE = re.compile(
    r"(?<=[.!?。])\s+|(?<=[" + _KO_ENDERS + r"])\s+"
)

# 인용 부호(곧은/굽은 큰따옴표).
_STRAIGHT_QUOTE = '"'
_CURLY_OPEN = "“"  # “
_CURLY_CLOSE = "”"  # ”

# 경어 수준 분류용 어미 패턴(문장 말미 기준).
_FORMAL_ENDINGS = ("습니다", "습니까", "ㅂ니다", "ㅂ니까", "십시오", "읍시다")
_POLITE_ENDINGS = ("어요", "아요", "에요", "예요", "이에요", "세요", "지요", "죠", "요")
_PLAIN_ENDINGS = ("는다", "ㄴ다", "었다", "았다", "이다", "었다.", "다", "까", "라", "자")


def split_sentences(text: str) -> list[str]:
    """한국어를 고려한 결정론적 문장 분리.

    마침표/물음표/느낌표(. ! ? 。) 또는 한국어 종결 어미가 공백·문자열 끝
    앞에 올 때 문장 경계로 본다. 빈 문장은 제거한다.
    """
    if not text:
        return []
    parts = _SPLIT_RE.split(text)
    return [p.strip() for p in parts if p and p.strip()]


def _classify_ending(sentence: str) -> str:
    """한 문장의 경어 수준을 분류한다: plain | polite | formal | other.

    종결부호(. ! ? " 등)를 떼어낸 말미로 판정한다. 결정론적.
    """
    s = sentence.strip()
    # 말미의 종결 부호/인용부호 제거.
    s = s.rstrip(".!?。”“\"'』」)] \t")
    if not s:
        return "other"
    for suf in _FORMAL_ENDINGS:
        if s.endswith(suf):
            return "formal"
    for suf in _POLITE_ENDINGS:
        if s.endswith(suf):
            return "polite"
    for suf in _PLAIN_ENDINGS:
        if s.endswith(suf):
            return "plain"
    return "other"


def _has_quote(sentence: str) -> bool:
    if _STRAIGHT_QUOTE in sentence:
        return True
    return _CURLY_OPEN in sentence or _CURLY_CLOSE in sentence


def style_vector(text: str) -> dict:
    """텍스트의 문체 특징 벡터를 계산한다. 결정론적·0분모 방어."""
    sentences = split_sentences(text)
    n = len(sentences)

    if n == 0:
        return {
            "sentence_count": 0,
            "avg_sentence_len": 0.0,
            "comma_rate": 0.0,
            "ending_dist": {"plain": 0.0, "polite": 0.0, "formal": 0.0, "other": 0.0},
            "quote_ratio": 0.0,
        }

    total_chars = sum(len(s) for s in sentences)
    total_commas = sum(s.count(",") + s.count("，") for s in sentences)

    counts = {"plain": 0, "polite": 0, "formal": 0, "other": 0}
    quoted = 0
    for s in sentences:
        counts[_classify_ending(s)] += 1
        if _has_quote(s):
            quoted += 1

    ending_dist = {k: v / n for k, v in counts.items()}

    return {
        "sentence_count": n,
        "avg_sentence_len": total_chars / n,
        "comma_rate": total_commas / n,
        "ending_dist": ending_dist,
        "quote_ratio": quoted / n,
    }


def _prose_blocks(blocks) -> list[Block]:
    return [b for b in blocks if b.block_type == "paragraph"]


def _block_text(block: Block) -> str:
    return block.polished_text or block.text


def detect_drift(blocks, z_threshold: float = 2.0) -> dict:
    """산문 블록의 평균 문장 길이로 z-score 이상치(문체 이탈)를 찾는다.

    블록이 2개 미만이거나 표준편차가 0이면 이상치가 없다고 본다.
    """
    prose = _prose_blocks(blocks)
    values = [
        (b.block_id, style_vector(_block_text(b))["avg_sentence_len"])
        for b in prose
    ]
    n = len(values)

    if n < 2:
        return {"mean": 0.0, "stdev": 0.0, "outliers": [], "ok": True, "n": n}

    nums = [v for _, v in values]
    mean = statistics.mean(nums)
    stdev = statistics.pstdev(nums)

    if stdev == 0:
        return {"mean": mean, "stdev": 0.0, "outliers": [], "ok": True, "n": n}

    outliers = []
    for block_id, value in values:
        z = (value - mean) / stdev
        if abs(z) > z_threshold:
            outliers.append({"block_id": block_id, "value": value, "z": z})

    return {
        "mean": mean,
        "stdev": stdev,
        "outliers": outliers,
        "ok": not outliers,
        "n": n,
    }


def drift_report(blocks) -> dict:
    """문체 이탈 리포트. 산문 블록 수와 이탈 감지 결과를 묶는다."""
    drift = detect_drift(blocks)
    return {
        "ok": drift["ok"],
        "drift": drift,
        "n_prose": len(_prose_blocks(blocks)),
    }
