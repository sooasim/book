"""In-memory RAG (retrieval) 모듈 (OCES 03 §3.4 RAG, 간소화·오프라인).

- 결정적: 임베딩은 `Provider.embed`(기본 StubProvider, 8차원 해시) 사용.
- 외부 의존성 없음(stdlib only). 네트워크/디스크 불필요.
- 검색은 코사인 유사도 기준 상위 k 반환.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ebook_polisher.llm_provider import Provider, StubProvider


@dataclass
class Source:
    """검색 가능한 근거 단위."""

    source_id: str
    text: str
    uri: str = ""
    embedding: list[float] = field(default_factory=list)


def cosine(a: list[float], b: list[float]) -> float:
    """코사인 유사도. 한쪽이라도 영벡터/빈벡터면 0.0(안전)."""
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


class SimpleVectorStore:
    """인메모리 벡터 스토어. provider.embed 로 임베딩을 계산/보관한다."""

    def __init__(self, provider: Provider | None = None):
        self.provider: Provider = provider if provider is not None else StubProvider()
        self.sources: list[Source] = []

    def add(self, source_id: str, text: str, uri: str = "") -> Source:
        embedding = list(self.provider.embed(text))
        src = Source(source_id=source_id, text=text, uri=uri, embedding=embedding)
        self.sources.append(src)
        return src

    def add_many(self, items: list[tuple[str, str]]) -> None:
        for source_id, text in items:
            self.add(source_id, text)

    def search(self, query: str, k: int = 5) -> list[tuple[Source, float]]:
        if not self.sources:
            return []
        q = list(self.provider.embed(query))
        scored = [(src, cosine(q, src.embedding)) for src in self.sources]
        # 코사인 내림차순. 동점은 입력 순서를 안정적으로 유지(안정 정렬).
        scored.sort(key=lambda pair: pair[1], reverse=True)
        if k < 0:
            k = 0
        return scored[:k]

    def __len__(self) -> int:
        return len(self.sources)


def rag_context(query: str, store: SimpleVectorStore, k: int = 3,
                max_chars: int = 800) -> str:
    """상위 k개 근거를 검색해 컨텍스트 블록 문자열로 포맷.

    형식:
        [근거]
        [source_id] text...
        [source_id2] ...
    max_chars 로 절단한다. 스토어가 비었으면 "" 반환.
    """
    if len(store) == 0:
        return ""
    results = store.search(query, k=k)
    if not results:
        return ""
    lines = ["[근거]"]
    for src, _score in results:
        lines.append(f"[{src.source_id}] {src.text}")
    block = "\n".join(lines)
    if len(block) > max_chars:
        block = block[:max_chars]
    return block


def build_store_from_sources(sources: list[dict],
                             provider: Provider | None = None) -> SimpleVectorStore:
    """딕셔너리 리스트로부터 스토어 구성. 각 항목은 id/text(선택 uri) 키를 가진다."""
    store = SimpleVectorStore(provider=provider)
    for item in sources:
        source_id = str(item["id"])
        text = str(item["text"])
        uri = str(item.get("uri", ""))
        store.add(source_id, text, uri)
    return store
