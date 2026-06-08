import unittest

from ebook_polisher.models import Block
from ebook_polisher.chunker import (
    estimate_tokens,
    tail_overlap,
    boundary_score,
    plan_chunks,
)
from ebook_polisher.verifier import verify_chunk_plan


def make_blocks(n=50):
    blocks = []
    for i in range(n):
        page = i // 5  # 5 블록마다 페이지 변경
        block_type = "title" if i % 5 == 0 else "paragraph"
        if i % 17 == 0 and i != 0:
            block_type = "table"
        blocks.append(
            Block(
                block_id=f"b{i:06d}",
                page_id=f"p{page:06d}",
                order_index=i % 5,
                block_type=block_type,
                text=f"문단 {i} 내용입니다. " * 20,  # 적당한 길이
            )
        )
    return blocks


class TestChunker(unittest.TestCase):
    def test_estimate_tokens(self):
        self.assertEqual(estimate_tokens(""), 1)
        self.assertEqual(estimate_tokens("abcd"), 2)
        self.assertEqual(estimate_tokens("a"), 1)

    def test_tail_overlap(self):
        blocks = make_blocks(10)
        tail = tail_overlap(blocks, overlap_tokens=50)
        self.assertTrue(len(tail) >= 1)
        # 꼬리에서 가져왔으므로 마지막 블록 포함.
        self.assertEqual(tail[-1].block_id, blocks[-1].block_id)

    def test_boundary_score_deterministic(self):
        b_title = Block("b1", "p000000", 0, "title", "x")
        b_para = Block("b2", "p000000", 1, "paragraph", "x")
        b_table = Block("b3", "p000000", 2, "table", "x")
        self.assertEqual(boundary_score(b_title), boundary_score(b_title))
        self.assertGreater(boundary_score(b_title), boundary_score(b_table))
        self.assertGreater(boundary_score(b_para), boundary_score(b_table))

    def test_plan_chunks_multiple_and_lossless(self):
        blocks = make_blocks(50)
        all_ids = [b.block_id for b in blocks]
        # 작은 max_tokens 로 여러 청크 강제.
        chunks = plan_chunks(blocks, max_tokens=400, overlap_tokens=100)
        self.assertGreater(len(chunks), 1, "여러 청크가 생성되어야 함")

        # chunk_id 형식 검사.
        for seq, chunk in enumerate(chunks, start=1):
            self.assertEqual(chunk.chunk_id, f"chunk_{seq:06d}")

        report = verify_chunk_plan(all_ids, chunks)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["duplicate_primary"], [])
        self.assertEqual(report["overlap_only"], [])
        self.assertEqual(report["coverage_ratio"], 1.0)

    def test_page_bounds(self):
        blocks = make_blocks(50)
        chunks = plan_chunks(blocks, max_tokens=400, overlap_tokens=100)
        for chunk in chunks:
            self.assertLessEqual(chunk.page_start, chunk.page_end)

    def test_single_chunk_when_small(self):
        blocks = make_blocks(3)
        all_ids = [b.block_id for b in blocks]
        chunks = plan_chunks(blocks, max_tokens=100000, overlap_tokens=100)
        self.assertEqual(len(chunks), 1)
        report = verify_chunk_plan(all_ids, chunks)
        self.assertTrue(report["ok"], report)


if __name__ == "__main__":
    unittest.main()
