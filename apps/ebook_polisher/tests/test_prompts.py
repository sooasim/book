import unittest

from ebook_polisher.prompts import (
    POLISH_SYSTEM_PROMPT,
    PromptGene,
    build_user_prompt,
    score_gene,
    select_prompt_genes,
)


def _gene(gid, score_inputs, token_cost):
    genre, task, success, tok_eff, recency = score_inputs
    return PromptGene(
        gene_id=gid,
        category="cat",
        content=f"content-{gid}",
        genre_match=genre,
        task_match=task,
        success_rate=success,
        token_efficiency=tok_eff,
        recency=recency,
        token_cost=token_cost,
    )


class TestPrompts(unittest.TestCase):
    def test_system_prompt_korean_editor(self):
        self.assertIn("편집자", POLISH_SYSTEM_PROMPT)
        self.assertIn("block_id", POLISH_SYSTEM_PROMPT)

    def test_build_user_prompt_contains_style_bible(self):
        bible = "[스타일 바이블]\n- 장르: 소설"
        payload = {"chunk_id": "c1", "blocks": [{"block_id": "b1", "text": "안녕"}]}
        prompt = build_user_prompt(bible, payload)
        self.assertIn(bible, prompt)
        self.assertIn("b1", prompt)

    def test_select_prompt_genes_within_budget_and_ordered(self):
        # 점수 순서: g_high > g_mid > g_low
        g_high = _gene("g_high", (0.9, 0.9, 0.9, 0.9, 0.9), token_cost=40)
        g_mid = _gene("g_mid", (0.6, 0.6, 0.6, 0.6, 0.6), token_cost=40)
        g_low = _gene("g_low", (0.1, 0.1, 0.1, 0.1, 0.1), token_cost=40)

        selected = select_prompt_genes([g_low, g_mid, g_high], token_budget=100)

        # 예산 100 / 각 40 → 2개만 들어감 (점수 상위 g_high, g_mid)
        total = sum(g.token_cost for g in selected)
        self.assertLessEqual(total, 100)
        self.assertEqual([g.gene_id for g in selected], ["g_high", "g_mid"])

        # 점수 내림차순 검증
        scores = [score_gene(g) for g in selected]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_select_prompt_genes_zero_budget(self):
        g = _gene("g", (0.9, 0.9, 0.9, 0.9, 0.9), token_cost=10)
        self.assertEqual(select_prompt_genes([g], token_budget=0), [])


if __name__ == "__main__":
    unittest.main()
