"""원장 저장소 (SQLite + 인메모리 인덱스).

파이프라인이 의존하는 Repository 계약(models.Repository)을 구현한다.
핵심 책임: 블록 원장 보관, 청크 페이로드 생성(세 겹 컨텍스트), 윤문 결과 저장,
감사 로그, 책 단위 coverage 검증, 최종 포맷 내보내기.

불변식(docs/07):
  - 각 블록은 정확히 한 청크의 primary 로만 윤문된다(overlap 은 컨텍스트일 뿐).
  - 검증은 페이지/블록 기준으로 되돌려 수행한다.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ebook_polisher.models import (
    AuditEvent,
    Block,
    Book,
    Chunk,
    Page,
    PolishResult,
    new_id,
    sha256_text,
)
from ebook_polisher.verifier import preserve_check, verify_polished_blocks

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SQLiteRepository:
    """SQLite 기반 저장소. db_path=":memory:" 면 인메모리."""

    def __init__(self, db_path: str = ":memory:", out_dir: str | None = None):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self.out_dir = Path(out_dir) if out_dir else None
        # 인메모리 인덱스(빠른 접근)
        self.book: Book | None = None
        self.blocks: dict[str, Block] = {}
        self.block_order: list[str] = []           # order_index 순 block_id
        self.block_page: dict[str, int] = {}        # block_id -> page_number
        self.page_numbers: list[int] = []           # 모든 페이지 번호(블록 없는 페이지 포함)
        self.done_chunks: set[str] = set()
        self.audit_log: list[AuditEvent] = []
        self.preservation_violations: list[dict] = []  # 금지 변경(숫자 등) 위반
        self.page_count: int = 0

    def _init_schema(self) -> None:
        if SCHEMA_PATH.exists():
            self.conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.conn.commit()

    # ---------------------------------------------------------------- 적재
    def _existing_polished(self) -> dict[str, str]:
        """재개: 이미 저장된 윤문 텍스트를 보존하기 위해 읽어둔다."""
        rows = self.conn.execute(
            "SELECT block_id, polished_text FROM blocks WHERE polished_text IS NOT NULL AND polished_text != ''"
        ).fetchall()
        return {r["block_id"]: r["polished_text"] for r in rows}

    def restore_progress(self, chunks: list[Chunk]) -> int:
        """primary 블록이 모두 윤문된 청크를 done 으로 표시(진짜 재개)."""
        restored = 0
        for chunk in chunks:
            ids = chunk.primary_block_ids
            if ids and all(
                (self.blocks.get(b) and self.blocks[b].polished_text != "") for b in ids
            ):
                self.done_chunks.add(chunk.chunk_id)
                restored += 1
        return restored

    def ingest(self, book: Book, pages: list[Page]) -> None:
        self.book = book
        self.page_count = len(pages)
        self.page_numbers = [p.page_number for p in pages]
        preserved = self._existing_polished()
        self.conn.execute(
            "INSERT OR REPLACE INTO books(book_id,title,author,genre,source_format,source_hash,created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (book.book_id, book.title, book.author, book.genre,
             book.source_format, book.source_hash, _now()),
        )
        for page in pages:
            self.conn.execute(
                "INSERT OR REPLACE INTO pages(page_id,book_id,page_number,chapter_id,raw_text,"
                "normalized_text,source_hash,output_hash,status) VALUES(?,?,?,?,?,?,?,?,?)",
                (page.page_id, book.book_id, page.page_number, page.chapter_id,
                 page.raw_text, page.normalized_text, page.source_hash, "", page.status),
            )
            for block in page.blocks:
                if block.block_id in preserved and not block.polished_text:
                    block.polished_text = preserved[block.block_id]
                    block.status = "polished"
                self.blocks[block.block_id] = block
                self.block_order.append(block.block_id)
                self.block_page[block.block_id] = page.page_number
                self.conn.execute(
                    "INSERT OR REPLACE INTO blocks(block_id,book_id,page_id,order_index,block_type,"
                    "raw_text,polished_text,source_hash,status) VALUES(?,?,?,?,?,?,?,?,?)",
                    (block.block_id, book.book_id, block.page_id, block.order_index,
                     block.block_type, block.text, block.polished_text, block.source_hash, block.status),
                )
        self.conn.commit()

    def all_block_ids(self) -> list[str]:
        return list(self.block_order)

    # ---------------------------------------------------------------- 파이프라인 계약
    def is_done(self, chunk_id: str) -> bool:
        return chunk_id in self.done_chunks

    def build_chunk_payload(self, chunk: Chunk) -> dict:
        """세 겹 컨텍스트 페이로드. source_blocks = PRIMARY 블록만(중복 윤문 방지)."""
        source_blocks = []
        for bid in chunk.primary_block_ids:
            block = self.blocks.get(bid)
            if block is None:
                continue
            source_blocks.append({
                "block_id": block.block_id,
                "page": self.block_page.get(bid, 0),
                "type": block.block_type,
                "text": block.text,
            })
        overlap_text = "\n".join(
            self.blocks[b].text for b in chunk.overlap_block_ids if b in self.blocks
        )
        return {
            "chunk_id": chunk.chunk_id,
            "book_context": {
                "title": self.book.title if self.book else "",
                "genre": self.book.genre if self.book else "",
            },
            "local_context": {"previous_overlap": overlap_text},
            "source_blocks": source_blocks,
        }

    def save_polished_chunk(self, chunk_id: str, result: PolishResult) -> None:
        for pblock in result.polished_blocks:
            block = self.blocks.get(pblock.block_id)
            if block is None:
                continue
            # 금지 변경 검사(숫자/URL/ISBN 등 보존) — 위반 시 기록(QA blocking 게이트)
            pres = preserve_check(block.text, pblock.polished_text)
            if not pres["ok"]:
                self.preservation_violations.append({"block_id": pblock.block_id, "detail": pres})
            block.polished_text = pblock.polished_text
            block.status = "polished"
            self.conn.execute(
                "UPDATE blocks SET polished_text=?, status='polished' WHERE block_id=?",
                (pblock.polished_text, pblock.block_id),
            )
        self.done_chunks.add(chunk_id)
        self.conn.commit()

    def audit(self, target_id: str, result: PolishResult) -> None:
        event = AuditEvent(
            event_id=new_id("ev_"),
            book_id=self.book.book_id if self.book else "",
            target_id=target_id,
            event_type="polish_chunk",
            after_hash=sha256_text(json.dumps(
                [b.polished_text for b in result.polished_blocks], ensure_ascii=False)),
            payload_json=json.dumps({"blocks": len(result.polished_blocks),
                                     "risk_flags": result.risk_flags}, ensure_ascii=False),
            created_at=_now(),
        )
        self.audit_log.append(event)
        self.conn.execute(
            "INSERT INTO audit_events(event_id,book_id,target_id,event_type,before_hash,after_hash,"
            "payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (event.event_id, event.book_id, event.target_id, event.event_type,
             event.before_hash, event.after_hash, event.payload_json, event.created_at),
        )
        self.conn.commit()

    def verify_book_coverage(self) -> dict:
        source_ids = self.all_block_ids()
        polished_ids = [bid for bid in source_ids if self.blocks[bid].polished_text != ""]
        report = verify_polished_blocks(source_ids, polished_ids)
        report["polished"] = len(polished_ids)
        report["source"] = len(source_ids)
        return report

    # ---------------------------------------------------------------- 내보내기
    def assemble_markdown(self) -> str:
        lines = []
        for bid in self.block_order:
            block = self.blocks[bid]
            text = block.polished_text or block.text
            if block.block_type == "title":
                lines.append(text if text.startswith("#") else f"# {text}")
            else:
                lines.append(text)
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def polished_page_count(self) -> int:
        """모든 블록이 윤문된 페이지 수. 블록이 없는 페이지는 자동 충족(all([])==True)."""
        by_page: dict[int, list[bool]] = {pn: [] for pn in self.page_numbers}
        for bid in self.block_order:
            pg = self.block_page[bid]
            by_page.setdefault(pg, []).append(self.blocks[bid].polished_text != "")
        return sum(1 for flags in by_page.values() if all(flags))

    def export_all_formats(self) -> dict:
        coverage = self.verify_book_coverage()
        if not coverage["ok"]:
            return {"ok": False, "reason": "coverage_failed", "coverage": coverage}
        md = self.assemble_markdown()
        files: dict[str, str] = {}
        if self.out_dir:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            md_path = self.out_dir / "polished.md"
            md_path.write_text(md, encoding="utf-8")
            files["md"] = str(md_path)
        return {"ok": True, "formats": ["md"], "files": files,
                "markdown_len": len(md), "coverage": coverage}
