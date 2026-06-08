import unittest

from ebook_polisher.agents import AGENCY_ROLES, run_agency_debate
from ebook_polisher.models import PolishedBlock, PolishResult


class FakePolisher:
    """주입용 가짜 폴리셔 — 알려진 PolishResult 를 반환한다."""

    def __init__(self, result):
        self._result = result

    def polish(self, payload, style_bible=""):
        return self._result


def fake_lint(text):
    """'BAD' 가 들어 있으면 실패(False)."""
    return "BAD" not in text


class TestAgents(unittest.TestCase):
    def _make_result(self):
        warned = PolishedBlock(
            block_id="b1",
            polished_text="정상 텍스트입니다.",
            warnings=["모호한 표현"],
        )
        bad = PolishedBlock(
            block_id="b2",
            polished_text="이 문장은 BAD 입니다.",
        )
        return PolishResult(chunk_id="c1", polished_blocks=[warned, bad])

    def test_debate_applies_crescent_and_risk_flag(self):
        result = self._make_result()
        polisher = FakePolisher(result)

        out = run_agency_debate({"chunk_id": "c1"}, polisher, fake_lint)

        by_id = {b.block_id: b for b in out.polished_blocks}
        # block_id 보존
        self.assertEqual(set(by_id), {"b1", "b2"})

        # E: 경고가 있는 b1 → crescent
        self.assertEqual(by_id["b1"].honest_marker, "crescent")
        # 경고 없는 b2 는 기본 star 유지
        self.assertEqual(by_id["b2"].honest_marker, "star")

        # J: BAD 를 포함한 b2 → risk_flag
        self.assertIn("hardfail:b2", out.risk_flags)
        self.assertNotIn("hardfail:b1", out.risk_flags)

    def test_no_crash_and_returns_polish_result(self):
        result = self._make_result()
        out = run_agency_debate({}, FakePolisher(result), fake_lint)
        self.assertIsInstance(out, PolishResult)
        self.assertEqual(out.chunk_id, "c1")

    def test_clean_result_no_flags(self):
        clean = PolishResult(
            chunk_id="c2",
            polished_blocks=[PolishedBlock(block_id="b1", polished_text="좋은 문장")],
        )
        out = run_agency_debate({}, FakePolisher(clean), fake_lint)
        self.assertEqual(out.risk_flags, [])
        self.assertEqual(out.polished_blocks[0].honest_marker, "star")

    def test_roles_defined(self):
        for role in ("A", "B", "C", "E", "F", "G", "J"):
            self.assertIn(role, AGENCY_ROLES)


if __name__ == "__main__":
    unittest.main()
