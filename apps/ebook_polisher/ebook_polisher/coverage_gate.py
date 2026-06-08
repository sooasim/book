"""커버리지 게이트 (Coverage Gate).

파이프라인 각 단계의 페이지 수가 source 와 모두 동일해야 export 가 열린다.
이것이 무손실을 보장하는 하드 게이트다(docs/07).
"""
from __future__ import annotations


def coverage_gate(stage_page_counts: dict) -> dict:
    """단계별 페이지 수 동일성 게이트.

    입력 예: {"source":3000,"parsed":3000,"chunked":3000,
              "polished":3000,"verified":3000,"assembled":3000}
    반환: ok(모든 값이 source 와 동일하며 >0), expected, stages_failed, detail.
    """
    expected = stage_page_counts.get("source", 0)
    stages_failed = sorted(
        name
        for name, count in stage_page_counts.items()
        if name != "source" and count != expected
    )
    all_positive = expected > 0 and all(
        count > 0 for count in stage_page_counts.values()
    )
    all_equal = all(
        count == expected for count in stage_page_counts.values()
    )
    ok = all_equal and all_positive
    detail = {name: count for name, count in stage_page_counts.items()}
    return {
        "ok": ok,
        "expected": expected,
        "stages_failed": stages_failed,
        "detail": detail,
    }
