import unittest

from ebook_polisher.models import MemoryItem
from ebook_polisher.memory import MemoryMatch, memory_score, select_memory


def _item(mid, importance=0.5):
    return MemoryItem(
        memory_id=mid,
        book_id="b1",
        layer=2,
        memory_type="term",
        content=f"content-{mid}",
        importance=importance,
    )


class TestMemory(unittest.TestCase):
    def test_ranks_high_similarity_importance_first(self):
        high = MemoryMatch(
            item=_item("high", importance=0.9),
            semantic_similarity=0.95,
            recency=0.9,
            chapter_relevance=0.9,
        )
        low = MemoryMatch(
            item=_item("low", importance=0.1),
            semantic_similarity=0.1,
            recency=0.1,
            chapter_relevance=0.1,
        )
        result = select_memory([low, high])
        self.assertEqual([m.memory_id for m in result], ["high", "low"])
        self.assertGreater(memory_score(high), memory_score(low))

    def test_respects_limit(self):
        matches = [
            MemoryMatch(
                item=_item(f"m{i}", importance=i / 10),
                semantic_similarity=i / 10,
                recency=0.5,
                chapter_relevance=0.5,
            )
            for i in range(10)
        ]
        result = select_memory(matches, limit=3)
        self.assertEqual(len(result), 3)
        # 상위 3개는 importance/similarity 가 가장 높은 m9, m8, m7
        self.assertEqual([m.memory_id for m in result], ["m9", "m8", "m7"])

    def test_score_weights(self):
        m = MemoryMatch(
            item=_item("x", importance=1.0),
            semantic_similarity=1.0,
            recency=1.0,
            chapter_relevance=1.0,
            user_pinned=1.0,
            validation_confidence=1.0,
        )
        self.assertAlmostEqual(memory_score(m), 1.0)


if __name__ == "__main__":
    unittest.main()
