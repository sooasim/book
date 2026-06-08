"""전체 파이프라인 (원장 기반, 재개 가능).

parse → ingest → chunk plan → (coverage) → polish(청크별) → save/audit
→ 책 coverage 검증 → 단계 coverage gate → export.

재개 가능: repo.is_done(chunk_id) 로 이미 처리한 청크는 건너뛴다(멱등).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from ebook_polisher.chunker import plan_chunks
from ebook_polisher.coverage_gate import coverage_gate
from ebook_polisher.models import Book, new_id, sha256_text
from ebook_polisher.qa_report import build_qa_report
from ebook_polisher.verifier import verify_chunk_plan


class CoverageError(RuntimeError):
    pass


class EbookPolisherPipeline:
    def __init__(self, parser, polisher, repository,
                 max_tokens: int = 12000, overlap_tokens: int = 800):
        self.parser = parser
        self.polisher = polisher
        self.repo = repository
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def run(self, source_path: str, style_bible: str = "", book: Book | None = None) -> dict:
        pages = self.parser.parse(source_path)
        if book is None:
            raw = "".join(p.raw_text for p in pages)
            book = Book(
                book_id=new_id("bk_"),
                title=os.path.basename(source_path),
                source_format=os.path.splitext(source_path)[1].lstrip(".").lower(),
                source_hash=sha256_text(raw),
                created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
        self.repo.ingest(book, pages)

        blocks = [b for p in pages for b in p.blocks]
        all_ids = [b.block_id for b in blocks]
        chunks = plan_chunks(blocks, max_tokens=self.max_tokens, overlap_tokens=self.overlap_tokens)

        plan_report = verify_chunk_plan(all_ids, chunks)
        if not plan_report["ok"]:
            raise CoverageError(f"Invalid chunk plan: {plan_report}")

        # 재개: 이미 윤문 완료된 청크는 건너뛴다(파일 DB 재오픈 시)
        if hasattr(self.repo, "restore_progress"):
            self.repo.restore_progress(chunks)

        processed = 0
        for chunk in chunks:
            if self.repo.is_done(chunk.chunk_id):
                continue
            payload = self.repo.build_chunk_payload(chunk)
            result = self.polisher.polish(payload, style_bible=style_bible)
            self.repo.save_polished_chunk(chunk.chunk_id, result)
            self.repo.audit(chunk.chunk_id, result)
            processed += 1

        book_cov = self.repo.verify_book_coverage()
        if not book_cov["ok"]:
            raise CoverageError(f"Book coverage failed: {book_cov}")

        n = len(pages)
        gate = coverage_gate({
            "source": n,
            "parsed": n,
            "chunked": n,
            "polished": self.repo.polished_page_count(),
            "assembled": n,
        })
        if not gate["ok"]:
            raise CoverageError(f"Coverage gate failed: {gate}")

        export = self.repo.export_all_formats()
        export["qa"] = build_qa_report(self.repo)
        export["pipeline"] = {
            "pages": n,
            "blocks": len(all_ids),
            "chunks": len(chunks),
            "processed_chunks": processed,
            "chunk_plan": plan_report,
            "coverage_gate": gate,
        }
        return export
