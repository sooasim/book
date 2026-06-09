"""Provider-agnostic LLM 계층 (OCES 02/03 문서).

- `Provider` 프로토콜: complete()/embed(). 모델 교체 가능한 추상화.
- `StubProvider`: 결정적·오프라인. API 키 없이 전체 파이프라인을 테스트/실행하기 위함.
- `AnthropicProvider`: Claude 연결 스켈레톤(키 있으면 사용). 기본 모델은 최신 Claude 권장.

라우팅 정책(03 §9): outline/edit→고품질(Opus), write→중급(Sonnet), factqa→중급/경량.
"""
from __future__ import annotations

import hashlib
import os
from typing import Protocol, runtime_checkable

# 단계별 권장 Claude 모델(03 §9). Provider 추상화로 교체 가능.
MODEL_ROUTING = {
    "outline": "claude-opus-4-8",
    "write": "claude-sonnet-4-6",
    "edit": "claude-opus-4-8",
    "factqa": "claude-sonnet-4-6",
    "default": "claude-sonnet-4-6",
}


@runtime_checkable
class Provider(Protocol):
    def complete(self, system: str, user: str, *, stage: str = "default",
                 max_tokens: int = 2000) -> str: ...
    def embed(self, text: str) -> list[float]: ...


class StubProvider:
    """결정적 오프라인 프로바이더.

    실제 LLM 없이도 파이프라인이 동작/테스트되도록 입력에서 결정적으로 텍스트를 만든다.
    같은 입력 → 같은 출력(해시 기반). 환각/네트워크 없음.
    """

    name = "stub"

    def complete(self, system: str, user: str, *, stage: str = "default",
                 max_tokens: int = 2000) -> str:
        # user 프롬프트에서 'TITLE::', 'BRIEF::', 'TARGET::' 힌트를 읽어 본문을 합성
        title = _extract(user, "TITLE::") or "본문"
        brief = _extract(user, "BRIEF::") or title
        carry = _extract(user, "CARRY::")
        target = _to_int(_extract(user, "TARGET::"), 180)
        seed = _extract(user, "TOPIC::") or title

        sentences: list[str] = []
        if carry:
            sentences.append(f"앞 장에서 다룬 내용을 이어받아, 이 장에서는 {brief}을(를) 다룬다.")
        sentences.append(f"{title}에서는 {seed}의 핵심을 살펴본다.")
        # 결정적 확장: 시드 해시로 문장 수를 정하되 입력이 같으면 동일
        h = int(hashlib.sha256((seed + brief + stage).encode("utf-8")).hexdigest(), 16)
        n = 3 + (h % 4)  # 3~6 문장
        for k in range(n):
            sentences.append(
                f"{brief}의 {k + 1}번째 측면은 독자가 {seed}을(를) 이해하는 데 도움이 된다."
            )
        text = " ".join(sentences)
        # 목표 분량 근사(문자 기준 과도하게 길면 자르지 않고 그대로 — 무손실은 윤문 단계가 보장)
        return text

    def embed(self, text: str) -> list[float]:
        # 결정적 의사 임베딩(해시 기반 8차원). RAG 골격 테스트용.
        h = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in h[:8]]


class AnthropicProvider:
    """Claude 연결 스켈레톤. ANTHROPIC_API_KEY 와 anthropic SDK 가 있을 때만 동작.

    네트워크가 필요하므로 테스트에서는 사용하지 않는다(StubProvider 사용).
    """

    name = "anthropic"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def complete(self, system: str, user: str, *, stage: str = "default",
                 max_tokens: int = 2000) -> str:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 가 없습니다. StubProvider 를 사용하세요.")
        try:
            import anthropic
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("anthropic SDK 미설치: pip install anthropic") from exc
        client = anthropic.Anthropic(api_key=self.api_key)
        model = MODEL_ROUTING.get(stage, MODEL_ROUTING["default"])
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")

    def embed(self, text: str) -> list[float]:  # pragma: no cover
        raise NotImplementedError("임베딩은 별도 임베딩 모델/프로바이더로 연결하세요.")


def get_provider(name: str = "stub") -> Provider:
    """이름으로 프로바이더 선택. 기본은 오프라인 결정적 StubProvider."""
    if name == "anthropic":
        return AnthropicProvider()
    return StubProvider()


# ------------------------------------------------------------------ helpers
def _extract(text: str, marker: str) -> str:
    for line in text.splitlines():
        if line.startswith(marker):
            return line[len(marker):].strip()
    return ""


def _to_int(s: str, default: int) -> int:
    try:
        return int(s)
    except (TypeError, ValueError):
        return default
