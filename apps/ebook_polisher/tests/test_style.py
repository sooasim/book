"""Style Bible (생성 지향 헬퍼) 테스트."""
from __future__ import annotations

import unittest

from ebook_polisher.style import (
    apply_glossary,
    build_style_bible,
    glossary_violations,
    render_style_bible,
)


class TestBuildStyleBible(unittest.TestCase):
    def test_returns_expected_keys(self):
        b = build_style_bible(
            audience="수학 입문 독자",
            tone="친근하고 명료한",
            honorific="polite",
            glossary={"리만 가설": ["리만가설"]},
            length_target=1200,
            banned=["결론적으로"],
        )
        self.assertEqual(
            set(b.keys()),
            {"audience", "tone", "honorific", "glossary", "length_target", "banned"},
        )
        self.assertEqual(b["audience"], "수학 입문 독자")
        self.assertEqual(b["tone"], "친근하고 명료한")
        self.assertEqual(b["honorific"], "polite")
        self.assertEqual(b["glossary"], {"리만 가설": ["리만가설"]})
        self.assertEqual(b["length_target"], 1200)
        self.assertEqual(b["banned"], ["결론적으로"])

    def test_defaults(self):
        b = build_style_bible()
        self.assertEqual(b["audience"], "")
        self.assertEqual(b["tone"], "")
        self.assertEqual(b["honorific"], "plain")
        self.assertEqual(b["glossary"], {})
        self.assertEqual(b["length_target"], 0)
        self.assertEqual(b["banned"], [])

    def test_invalid_honorific_falls_back(self):
        b = build_style_bible(honorific="nonsense")
        self.assertEqual(b["honorific"], "plain")

    def test_glossary_string_variant_normalized_to_list(self):
        b = build_style_bible(glossary={"리만 가설": "리만가설"})
        self.assertEqual(b["glossary"], {"리만 가설": ["리만가설"]})


class TestRenderStyleBible(unittest.TestCase):
    def test_includes_audience_tone_honorific_and_glossary(self):
        b = build_style_bible(
            audience="수학 입문 독자",
            tone="친근한",
            honorific="formal",
            glossary={"리만 가설": ["리만가설", "Riemann 가설"]},
        )
        out = render_style_bible(b)
        self.assertIn("[STYLE BIBLE]", out)
        self.assertIn("수학 입문 독자", out)
        self.assertIn("친근한", out)
        # 한국어 종결 라벨
        self.assertIn("하십시오체", out)
        # 용어집 정규 용어가 나열됨
        self.assertIn("리만 가설", out)

    def test_honorific_labels(self):
        self.assertIn("평서체", render_style_bible(build_style_bible(honorific="plain")))
        self.assertIn("해요체", render_style_bible(build_style_bible(honorific="polite")))
        self.assertIn(
            "하십시오체", render_style_bible(build_style_bible(honorific="formal"))
        )

    def test_empty_fields_omitted(self):
        # honorific 은 항상 기본값이 있으므로, 나머지 섹션 생략을 확인한다.
        out = render_style_bible(build_style_bible())
        self.assertNotIn("독자층", out)
        self.assertNotIn("톤", out)
        self.assertNotIn("용어 통일", out)
        self.assertNotIn("금칙어", out)
        self.assertNotIn("목표 분량", out)

    def test_length_and_banned_rendered(self):
        out = render_style_bible(
            build_style_bible(length_target=1200, banned=["결론적으로"])
        )
        self.assertIn("목표 분량: 1200단어", out)
        self.assertIn("금칙어: 결론적으로", out)


class TestApplyGlossary(unittest.TestCase):
    def test_replaces_variants_with_canonical(self):
        glossary = {"리만 가설": ["리만가설", "Riemann 가설"]}
        out = apply_glossary("리만가설은 Riemann 가설", glossary)
        self.assertEqual(out, "리만 가설은 리만 가설")

    def test_numbers_untouched(self):
        glossary = {"리만 가설": ["리만가설"]}
        out = apply_glossary("리만가설 2026년", glossary)
        self.assertEqual(out, "리만 가설 2026년")

    def test_empty_glossary_returns_input_unchanged(self):
        self.assertEqual(apply_glossary("그대로", {}), "그대로")
        self.assertEqual(apply_glossary("그대로", None), "그대로")

    def test_longer_variant_replaced_first(self):
        # "초끈 이론" 이 "끈 이론" 보다 먼저 치환되어 부분 겹침을 피한다.
        # 짧은 변형부터 치환하면 "초끈 이론" 의 "끈 이론" 이 먼저 잡혀
        # "초A" 같은 잘못된 결과가 난다. 길이 내림차순 정렬이 이를 막는다.
        glossary = {"끈 이론": ["string theory", "끈 이론"], "초끈 이론": ["초끈이론"]}
        out = apply_glossary("초끈이론과 string theory", glossary)
        self.assertEqual(out, "초끈 이론과 끈 이론")


class TestGlossaryViolations(unittest.TestCase):
    def test_detects_remaining_variant(self):
        glossary = {"리만 가설": ["리만가설"]}
        v = glossary_violations("리만가설은 어렵다", glossary)
        self.assertEqual(v, [{"found": "리만가설", "canonical": "리만 가설"}])

    def test_none_when_canonical(self):
        glossary = {"리만 가설": ["리만가설"]}
        self.assertEqual(glossary_violations("리만 가설은 어렵다", glossary), [])

    def test_empty_glossary(self):
        self.assertEqual(glossary_violations("아무 텍스트", {}), [])
        self.assertEqual(glossary_violations("아무 텍스트", None), [])


class TestDeterminism(unittest.TestCase):
    def test_same_inputs_same_outputs(self):
        kwargs = dict(
            audience="독자",
            tone="톤",
            honorific="polite",
            glossary={"리만 가설": ["리만가설", "Riemann 가설"]},
            length_target=500,
            banned=["금칙"],
        )
        b1 = build_style_bible(**kwargs)
        b2 = build_style_bible(**kwargs)
        self.assertEqual(b1, b2)
        self.assertEqual(render_style_bible(b1), render_style_bible(b2))

        text = "리만가설과 Riemann 가설"
        self.assertEqual(
            apply_glossary(text, kwargs["glossary"]),
            apply_glossary(text, kwargs["glossary"]),
        )
        self.assertEqual(
            glossary_violations(text, kwargs["glossary"]),
            glossary_violations(text, kwargs["glossary"]),
        )


if __name__ == "__main__":
    unittest.main()
