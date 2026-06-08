"""인-패키지 Hard-Fail 게이트 (제로존 방법론, 무손실 엔진).

AI가 생성/윤문한 텍스트가 다음 단계로 넘어가기 전 반드시 통과해야 하는 룰 기반 관문.
하나라도 FAIL이면 해당 Chunk는 강제 재작업(Retry) 대상이다.

검증 항목:
  - 빈 텍스트/빈 청크 (fail)
  - 괄호/따옴표 짝 불일치  ( ) [ ] { } “ ” ‘ ’ 「 」 『 』 (fail)
  - 닫히지 않은 굵게(**) 마크업 (fail)
  - 닫히지 않은 코드펜스(```) (fail)
  - 금지어(critical) 1회라도 검출 (fail)
  - 상투어(warn) 임계치(1만 자당) 초과 (fail), 그 외 경고

결정론적(deterministic)이며 표준 라이브러리만 사용한다.

사용:
  from ebook_polisher.hardfail import lint
  report = lint(text)   # {"ok": bool, "failures": [...], "warnings": [...], "stats": {...}}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# resources/hardfail/forbidden_terms.json 위치(저장소 루트 기준).
# .../book/apps/ebook_polisher/ebook_polisher/hardfail.py -> parents[3] == book
_REPO_ROOT = Path(__file__).resolve().parents[3]
_TERMS_PATH = _REPO_ROOT / "resources" / "hardfail" / "forbidden_terms.json"

PAIRS = [
    ("(", ")"), ("[", "]"), ("{", "}"),
    ("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』"),
]

# 금지어 파일이 없을 때 사용할 내장 폴백.
_FALLBACK_TERMS = {
    "critical": ["결론적으로 말하자면", "요약하자면"],
    "warn": ["결론적으로", "중요한 것은"],
    "ai_cliche_patterns": [],
    "severity_rules": {"warn_terms_max_per_10k": 3},
}


def _load_terms() -> dict:
    """금지어 사전 로드. 파일이 있으면 사용, 없으면 내장 폴백."""
    if _TERMS_PATH.exists():
        try:
            return json.loads(_TERMS_PATH.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return dict(_FALLBACK_TERMS)
    return dict(_FALLBACK_TERMS)


def _strip_inline_code(text: str) -> str:
    """코드펜스/인라인 코드는 구절 검사에서 제외해 오탐을 줄인다."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", " ", text)
    return text


def _add_fail(report: dict, code: str, msg: str, **extra) -> None:
    report["failures"].append({"code": code, "message": msg, **extra})
    report["ok"] = False


def _add_warn(report: dict, code: str, msg: str, **extra) -> None:
    report["warnings"].append({"code": code, "message": msg, **extra})


def _check_empty(text: str, report: dict) -> None:
    if not text or not text.strip():
        _add_fail(report, "empty_chunk", "빈 텍스트/빈 청크입니다.")


def _check_brackets(text: str, report: dict) -> None:
    for open_c, close_c in PAIRS:
        o, c = text.count(open_c), text.count(close_c)
        if o != c:
            _add_fail(
                report, "bracket_mismatch",
                f"짝 불일치: '{open_c}'={o} / '{close_c}'={c}",
                opener=open_c, closer=close_c,
            )


def _check_markdown(text: str, report: dict) -> None:
    if text.count("```") % 2 != 0:
        _add_fail(report, "md_fence_unclosed", "코드펜스(```)가 닫히지 않았습니다.")
    # 코드펜스를 제거한 뒤 굵게(**) 토큰 수가 홀수면 깨짐.
    no_fence = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    bold = len(re.findall(r"\*\*", no_fence))
    if bold % 2 != 0:
        _add_fail(report, "md_bold_unclosed", "굵게(**) 마크업이 닫히지 않았습니다.")


def _check_forbidden(text: str, terms: dict, report: dict) -> None:
    scan = _strip_inline_code(text)
    char_count = max(1, len(scan))
    # critical: 1회라도 검출 시 Hard-Fail.
    for term in terms.get("critical", []):
        n = scan.count(term)
        if n > 0:
            _add_fail(
                report, "forbidden_critical",
                f"금지어(critical) '{term}' {n}회 검출", term=term, count=n,
            )
    # warn: 1만 자당 허용치 초과 시 Hard-Fail, 그 외 경고.
    max_per_10k = terms.get("severity_rules", {}).get("warn_terms_max_per_10k", 3)
    budget = max(max_per_10k, int(round(char_count / 10000 * max_per_10k)))
    total_warn = 0
    detail: dict[str, int] = {}
    for term in terms.get("warn", []):
        n = scan.count(term)
        if n:
            detail[term] = n
            total_warn += n
    if total_warn > budget:
        _add_fail(
            report, "forbidden_warn_over_budget",
            f"상투어 총 {total_warn}회 > 허용 {budget}회", detail=detail,
        )
    elif total_warn:
        _add_warn(
            report, "forbidden_warn",
            f"상투어 {total_warn}회(허용 {budget})", detail=detail,
        )
    # 정규식 클리셰(있으면 경고).
    for pat in terms.get("ai_cliche_patterns", []):
        try:
            m = re.findall(pat, scan)
        except re.error:
            continue
        if m:
            _add_warn(
                report, "ai_cliche",
                f"AI 상투 패턴 검출: /{pat}/ ×{len(m)}", pattern=pat, count=len(m),
            )


def lint(text: str, terms: dict | None = None) -> dict:
    """텍스트를 Hard-Fail 게이트로 검사한다.

    Returns:
        {"ok": bool, "failures": list[dict], "warnings": list[dict], "stats": dict}
    """
    terms = terms if terms is not None else _load_terms()
    report: dict = {"ok": True, "failures": [], "warnings": [], "stats": {}}

    _check_empty(text, report)
    if not report["ok"]:
        report["stats"] = {"chars": len(text or "")}
        return report

    _check_brackets(text, report)
    _check_markdown(text, report)
    _check_forbidden(text, terms, report)

    report["stats"] = {
        "chars": len(text),
        "failures": len(report["failures"]),
        "warnings": len(report["warnings"]),
    }
    return report
