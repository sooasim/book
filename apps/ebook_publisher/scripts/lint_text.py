#!/usr/bin/env python3
"""
Hard-Fail 게이트웨이 린터 (아키텍처 v2.0 — 제로존 방법론).

AI가 생성/윤문한 텍스트가 다음 단계로 넘어가기 전 반드시 통과해야 하는 룰 기반 관문.
하나라도 FAIL이면 해당 Chunk는 강제 재작업(Retry) 대상이다.

검증 항목:
  - 금지어/AI 상투어 (resources/hardfail/forbidden_terms.json)
  - 괄호/따옴표 짝 불일치  ( ) [ ] { } “ ” ‘ ’ 「 」 『 』
  - 마크다운 깨짐: 닫히지 않은 ** , 코드펜스(```), 표 구분 행 오류
  - 빈 텍스트/빈 청크
  - 정직 봉인(Honest Boxing) 누락 경고: 임의 해석 신호가 있는데 ◑ 마커 없음

사용:
  from lint_text import lint_text
  report = lint_text(text)        # report.ok / report.failures / report.warnings
  report = lint_text(text, body_only=True)

CLI:
  python3 lint_text.py path/to/text.md
  python3 lint_text.py --selftest
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TERMS_PATH = REPO_ROOT / "resources" / "hardfail" / "forbidden_terms.json"

PAIRS = [("(", ")"), ("[", "]"), ("{", "}"),
         ("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』")]

# 임의 해석/추정 신호어: 있으면 ◑(honest box) 마커를 기대
HONEST_SIGNALS = ["추정", "아마도", "것으로 보인다", "라고 해석", "임의로", "불명확", "모호"]


@dataclass
class LintReport:
    ok: bool = True
    failures: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add_fail(self, code: str, msg: str, **extra) -> None:
        self.failures.append({"code": code, "message": msg, **extra})
        self.ok = False

    def add_warn(self, code: str, msg: str, **extra) -> None:
        self.warnings.append({"code": code, "message": msg, **extra})

    def to_dict(self) -> dict:
        return asdict(self)


def _load_terms() -> dict:
    if TERMS_PATH.exists():
        return json.loads(TERMS_PATH.read_text(encoding="utf-8"))
    return {"critical": [], "warn": [], "ai_cliche_patterns": [],
            "severity_rules": {"warn_terms_max_per_10k": 3}}


def _strip_inline_code(text: str) -> str:
    """코드펜스/인라인 코드는 검사에서 제외해 오탐을 줄인다."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", " ", text)
    return text


def check_brackets(text: str, report: LintReport) -> None:
    for open_c, close_c in PAIRS:
        o, c = text.count(open_c), text.count(close_c)
        if o != c:
            report.add_fail("bracket_mismatch",
                            f"짝 불일치: '{open_c}'={o} / '{close_c}'={c}",
                            opener=open_c, closer=close_c)


def check_markdown(text: str, report: LintReport) -> None:
    if text.count("```") % 2 != 0:
        report.add_fail("md_fence_unclosed", "코드펜스(```)가 닫히지 않았습니다.")
    # 굵게(**) 토큰 수가 홀수면 깨짐
    bold = len(re.findall(r"\*\*", text))
    if bold % 2 != 0:
        report.add_fail("md_bold_unclosed", "굵게(**) 마크업이 닫히지 않았습니다.")
    # 표 헤더 구분행 형식 오류(파이프는 있는데 --- 구분이 없는 표)
    for block in re.findall(r"(?:^\|.*\|\s*$\n?){2,}", text, flags=re.MULTILINE):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) >= 2 and not re.match(r"^\|[\s:|-]+\|\s*$", lines[1]):
            report.add_warn("md_table_header", "표 구분행(---) 형식이 의심됩니다.")
            break


def check_empty(text: str, report: LintReport) -> None:
    if not text or not text.strip():
        report.add_fail("empty_chunk", "빈 텍스트/빈 청크입니다.")


def check_forbidden(text: str, terms: dict, report: LintReport) -> None:
    scan = _strip_inline_code(text)
    char_count = max(1, len(scan))
    # critical: 1회라도 검출 시 Hard-Fail
    for term in terms.get("critical", []):
        n = scan.count(term)
        if n > 0:
            report.add_fail("forbidden_critical",
                            f"금지어(critical) '{term}' {n}회 검출", term=term, count=n)
    # warn: 임계치(1만 자당) 초과 시 Hard-Fail, 그 외 경고
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
        report.add_fail("forbidden_warn_over_budget",
                        f"상투어 총 {total_warn}회 > 허용 {budget}회", detail=detail)
    elif total_warn:
        report.add_warn("forbidden_warn", f"상투어 {total_warn}회(허용 {budget})", detail=detail)
    # 정규식 클리셰
    for pat in terms.get("ai_cliche_patterns", []):
        m = re.findall(pat, scan)
        if m:
            report.add_warn("ai_cliche", f"AI 상투 패턴 검출: /{pat}/ ×{len(m)}", pattern=pat, count=len(m))


def check_honest_boxing(text: str, report: LintReport) -> None:
    has_signal = any(s in text for s in HONEST_SIGNALS)
    has_marker = ("◑" in text) or ("honest" in text.lower())
    if has_signal and not has_marker:
        report.add_warn("honest_box_missing",
                        "임의 해석/추정 신호가 있으나 ◑(honest box) 마커가 없습니다. 재검토 권장.")


def lint_text(text: str, body_only: bool = False, terms: dict | None = None) -> LintReport:
    """텍스트를 Hard-Fail 게이트로 검사한다. body_only=True면 메타/서지 검사는 호출측 책임."""
    terms = terms if terms is not None else _load_terms()
    report = LintReport()
    check_empty(text, report)
    if not report.ok:
        report.stats = {"chars": len(text or "")}
        return report
    check_brackets(text, report)
    check_markdown(text, report)
    check_forbidden(text, terms, report)
    check_honest_boxing(text, report)
    report.stats = {"chars": len(text), "failures": len(report.failures),
                    "warnings": len(report.warnings)}
    return report


# ---------------------------------------------------------------- self-test
_SELFTESTS = [
    ("정상 문장입니다. 그는 천천히 걸었다.", True),
    ("결론적으로 말하자면 이것은 좋다.", False),          # critical 금지어
    ("괄호가 열렸지만 닫히지 않았다 (예시", False),        # bracket
    ("굵게 **가 닫히지 않음", False),                      # md bold
    ("", False),                                          # empty
    ("이 연구는 우리에게 진실을 보여준다.", True),         # warn 패턴(경고지만 ok)
]


def _selftest() -> int:
    failed = 0
    for text, expect_ok in _SELFTESTS:
        r = lint_text(text)
        mark = "OK" if r.ok == expect_ok else "MISMATCH"
        if r.ok != expect_ok:
            failed += 1
        print(f"[{mark}] expect_ok={expect_ok} got={r.ok}  :: {text[:30]!r}  "
              f"fails={[f['code'] for f in r.failures]}")
    print(f"\n셀프테스트: {len(_SELFTESTS) - failed}/{len(_SELFTESTS)} 통과")
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "--selftest":
        return _selftest()
    path = Path(argv[0])
    if not path.exists():
        print(f"파일 없음: {path}", file=sys.stderr)
        return 2
    report = lint_text(path.read_text(encoding="utf-8"))
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
