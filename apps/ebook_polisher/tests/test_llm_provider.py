"""LLM Provider 테스트 — Stub 결정성/임베딩/이미지 + Claude 경로(주입 모킹)."""
from __future__ import annotations

import unittest

from ebook_polisher.llm_provider import (
    MODEL_ROUTING,
    AnthropicProvider,
    StubProvider,
    get_provider,
)


class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeMessages:
    def __init__(self, sink):
        self.sink = sink

    def create(self, *, model, max_tokens, system, messages):
        self.sink["model"] = model
        self.sink["system"] = system
        self.sink["user"] = messages[0]["content"]
        return type("Resp", (), {"content": [_FakeBlock("클로드 응답: "), _FakeBlock(model)]})()


class _FakeClient:
    def __init__(self, sink):
        self.messages = _FakeMessages(sink)


class TestProviders(unittest.TestCase):
    def test_stub_deterministic(self):
        p = StubProvider()
        u = "TITLE::1장\nTOPIC::수학\nBRIEF::개요\nTARGET::100\nCARRY::"
        self.assertEqual(p.complete("sys", u), p.complete("sys", u))

    def test_stub_embed_and_image(self):
        p = StubProvider()
        self.assertEqual(len(p.embed("hello")), 8)
        img = p.image("표지", seed="제로존")
        self.assertTrue(img.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(p.image("x", seed="제로존"), p.image("y", seed="제로존"))

    def test_get_provider_default_stub(self):
        self.assertIsInstance(get_provider(), StubProvider)
        self.assertIsInstance(get_provider("anthropic"), AnthropicProvider)

    def test_anthropic_injected_client(self):
        sink = {}
        prov = AnthropicProvider(api_key="", client=_FakeClient(sink))
        out = prov.complete("시스템", "유저", stage="outline", max_tokens=123)
        # 단계별 모델 라우팅이 적용되는지
        self.assertEqual(sink["model"], MODEL_ROUTING["outline"])
        self.assertEqual(sink["system"], "시스템")
        self.assertIn("클로드 응답", out)
        self.assertIn(MODEL_ROUTING["outline"], out)

    def test_anthropic_without_key_or_client_raises(self):
        prov = AnthropicProvider(api_key="")
        with self.assertRaises(RuntimeError):
            prov.complete("s", "u")


if __name__ == "__main__":
    unittest.main()
