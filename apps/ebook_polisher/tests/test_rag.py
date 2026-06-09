"""rag 모듈 테스트 (unittest, 결정적: StubProvider)."""
import unittest

from ebook_polisher.llm_provider import StubProvider
from ebook_polisher.rag import (
    Source,
    SimpleVectorStore,
    build_store_from_sources,
    cosine,
    rag_context,
)


class TestCosine(unittest.TestCase):
    def test_identical_vectors(self):
        v = [0.1, 0.2, 0.3, 0.4]
        self.assertAlmostEqual(cosine(v, v), 1.0, places=9)

    def test_orthogonal(self):
        self.assertAlmostEqual(cosine([1.0, 0.0], [0.0, 1.0]), 0.0, places=9)

    def test_zero_vector_safe(self):
        self.assertEqual(cosine([0.0, 0.0], [1.0, 2.0]), 0.0)
        self.assertEqual(cosine([], [1.0, 2.0]), 0.0)
        self.assertEqual(cosine([1.0, 2.0], []), 0.0)


class TestSimpleVectorStore(unittest.TestCase):
    def test_add_and_len(self):
        store = SimpleVectorStore()
        self.assertEqual(len(store), 0)
        src = store.add("a", "첫 번째 텍스트")
        self.assertIsInstance(src, Source)
        self.assertEqual(src.source_id, "a")
        self.assertTrue(src.embedding)  # 임베딩이 계산됨
        self.assertEqual(len(store), 1)
        store.add("b", "두 번째 텍스트")
        self.assertEqual(len(store), 2)

    def test_add_many(self):
        store = SimpleVectorStore()
        store.add_many([("x", "텍스트 하나"), ("y", "텍스트 둘")])
        self.assertEqual(len(store), 2)

    def test_search_returns_most_similar_first(self):
        store = SimpleVectorStore()
        store.add("a", "사과는 빨간 과일이다")
        store.add("b", "바다는 푸르고 넓다")
        store.add("c", "산은 높고 험준하다")
        # 쿼리가 한 소스와 동일 → 동일 임베딩 → 코사인 ~1.0 으로 top-1
        results = store.search("바다는 푸르고 넓다", k=3)
        self.assertEqual(len(results), 3)
        top_src, top_score = results[0]
        self.assertEqual(top_src.source_id, "b")
        self.assertAlmostEqual(top_score, 1.0, places=9)

    def test_search_k_limit(self):
        store = SimpleVectorStore()
        for i in range(5):
            store.add(f"s{i}", f"고유한 텍스트 {i}")
        results = store.search("고유한 텍스트 0", k=2)
        self.assertEqual(len(results), 2)

    def test_search_empty_store(self):
        store = SimpleVectorStore()
        self.assertEqual(store.search("무엇이든", k=3), [])

    def test_custom_provider(self):
        store = SimpleVectorStore(provider=StubProvider())
        store.add("a", "텍스트")
        self.assertEqual(len(store), 1)


class TestRagContext(unittest.TestCase):
    def test_empty_store(self):
        store = SimpleVectorStore()
        self.assertEqual(rag_context("질문", store), "")

    def test_non_empty_contains_top_id(self):
        store = SimpleVectorStore()
        store.add("a", "사과는 빨간 과일이다")
        store.add("b", "바다는 푸르고 넓다")
        store.add("c", "산은 높고 험준하다")
        ctx = rag_context("바다는 푸르고 넓다", store, k=3)
        self.assertIn("[근거]", ctx)
        self.assertIn("[b]", ctx)  # top source_id 포함

    def test_max_chars_respected(self):
        store = SimpleVectorStore()
        for i in range(10):
            store.add(f"s{i}", "아주 긴 텍스트 " * 50 + str(i))
        max_chars = 120
        ctx = rag_context("아주 긴 텍스트 0", store, k=10, max_chars=max_chars)
        self.assertLessEqual(len(ctx), max_chars + 5)  # 작은 여유 허용


class TestBuildStore(unittest.TestCase):
    def test_build_from_sources(self):
        sources = [
            {"id": "a", "text": "첫 텍스트", "uri": "u://a"},
            {"id": "b", "text": "둘 텍스트"},
        ]
        store = build_store_from_sources(sources)
        self.assertEqual(len(store), 2)
        results = store.search("첫 텍스트", k=1)
        self.assertEqual(results[0][0].source_id, "a")
        self.assertEqual(results[0][0].uri, "u://a")


if __name__ == "__main__":
    unittest.main()
