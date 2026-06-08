"""명령줄 진입점 — 원클릭 윤문.

사용:
  cd apps/ebook_polisher
  python3 -m ebook_polisher.cli INPUT.md --out OUTDIR [--db polish.db] [--mode rules|agency]

내부는 다단계지만 사용자는 한 번 실행한다(docs/07 §12 원클릭 UX).
"""
from __future__ import annotations

import argparse
import json
import sys

from ebook_polisher.agents import run_agency_debate
from ebook_polisher.hardfail import lint
from ebook_polisher.parser import TextParser
from ebook_polisher.pipeline import EbookPolisherPipeline
from ebook_polisher.polisher import RulesPolisher
from ebook_polisher.repository import SQLiteRepository


class AgencyPolisher:
    """7-Agency 토론으로 RulesPolisher 를 감싼 폴리셔(결정적)."""

    def __init__(self) -> None:
        self._base = RulesPolisher()

    def polish(self, payload: dict, style_bible: str = ""):
        return run_agency_debate(payload, self._base, lint)


def build_pipeline(mode: str, db_path: str, out_dir: str) -> EbookPolisherPipeline:
    polisher = AgencyPolisher() if mode == "agency" else RulesPolisher()
    repo = SQLiteRepository(db_path=db_path, out_dir=out_dir)
    return EbookPolisherPipeline(parser=TextParser(), polisher=polisher, repository=repo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ink&Press v3 — 원장 기반 무손실 윤문 엔진")
    parser.add_argument("input", help="원고 파일 (.txt/.md)")
    parser.add_argument("--out", default="out", help="출력 폴더")
    parser.add_argument("--db", default=":memory:", help="SQLite 경로(재개하려면 파일 경로)")
    parser.add_argument("--mode", choices=["rules", "agency"], default="rules")
    args = parser.parse_args(argv)

    pipeline = build_pipeline(args.mode, args.db, args.out)
    result = pipeline.run(args.input)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
