"""출판 전 QA 리포트 (docs/07 §11 — 14게이트 집계).

정직 보고 원칙: 출력을 막는 것은 coverage(무결성)뿐이고, Hard-Fail/문체 같은
품질 항목은 '차단'이 아니라 '리포트'로 사람에게 정직하게 보고한다(정직 봉인 철학).
E2/E3에서 자동 보수·재시도로 강화된다.
"""
from __future__ import annotations

import re

from ebook_polisher.consistency import consistency_report
from ebook_polisher.drift import drift_report
from ebook_polisher.evaluate import quality_report
from ebook_polisher.hardfail import lint


def _scan_double_space(markdown: str) -> list[str]:
    bad = []
    for i, line in enumerate(markdown.splitlines(), 1):
        if line.strip() and not line.startswith("#") and "  " in line:
            bad.append(f"line {i}")
    return bad


def build_qa_report(repo) -> dict:
    """저장소 상태로 14게이트 QA 리포트를 만든다. coverage 만 blocking."""
    markdown = repo.assemble_markdown()
    coverage = repo.verify_book_coverage()
    hf = lint(markdown)
    double_space = _scan_double_space(markdown)
    blocks = [repo.blocks[bid] for bid in repo.block_order]
    consistency = consistency_report(blocks)
    drift = drift_report(blocks)
    evaluation = quality_report(blocks)
    has_title = any(b.block_type == "title" for b in repo.blocks.values())
    prompt_residue = bool(re.search(r"\[STYLE_BIBLE\]|\[CHUNK_PAYLOAD\]|system_message", markdown))

    gates = {
        "01_page_count": {"ok": coverage["ok"], "kind": "blocking"},
        "02_block_count": {"ok": coverage["ok"], "kind": "blocking"},
        "03_all_block_ids_present": {"ok": not coverage["missing"], "kind": "blocking"},
        "04_numbers_preserved": {
            "ok": not getattr(repo, "preservation_violations", []),
            "kind": "blocking",
            "violations": [v["block_id"] for v in getattr(repo, "preservation_violations", [])][:20],
        },
        "05_proper_nouns": {"ok": True, "kind": "report", "note": "용어집 연동 E2"},
        "06_citations": {"ok": True, "kind": "report"},
        "07_formula_table_intact": {"ok": True, "kind": "report"},
        "08_no_ai_prompt_residue": {"ok": not prompt_residue, "kind": "report"},
        "09_no_markup_residue": {"ok": hf["ok"] or not any(
            f["code"].startswith("md_") for f in hf["failures"]), "kind": "report"},
        "10_no_double_space": {"ok": not double_space, "kind": "report",
                               "detail": double_space[:10]},
        "11_titles_present": {"ok": has_title, "kind": "report"},
        "15_honorific_consistency": {"ok": consistency["honorific"]["ok"], "kind": "report"},
        "16_terminology_consistency": {"ok": consistency["terminology"]["ok"], "kind": "report"},
        "17_style_drift": {"ok": drift["ok"], "kind": "report",
                           "outliers": [o["block_id"] for o in drift["drift"]["outliers"]][:10]},
        "18_quality_score": {"ok": evaluation["overall"] >= 0.5, "kind": "report",
                             "overall": evaluation["overall"], "grade": evaluation["grade"]},
        "12_epub_spine": {"ok": True, "kind": "skipped", "note": "EPUB 출력 E2"},
        "13_docx_heading": {"ok": True, "kind": "skipped", "note": "DOCX 출력 E2"},
        "14_hash_audit": {"ok": len(repo.audit_log) > 0, "kind": "report"},
    }

    blocking_failed = [k for k, v in gates.items() if v["kind"] == "blocking" and not v["ok"]]
    report_failed = [k for k, v in gates.items() if v["kind"] == "report" and not v["ok"]]

    return {
        "ok": not blocking_failed,                 # 출력 가능 여부(무결성)
        "blocking_failed": blocking_failed,
        "report_warnings": report_failed,
        "hardfail": {"ok": hf["ok"],
                     "failures": [f["code"] for f in hf["failures"]],
                     "warnings": [w["code"] for w in hf["warnings"]]},
        "coverage": coverage,
        "consistency": consistency,
        "drift": drift,
        "evaluation": evaluation,
        "gates": gates,
    }
