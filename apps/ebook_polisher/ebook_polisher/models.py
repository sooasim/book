"""핵심 데이터 모델 및 인터페이스 계약 (Ink&Press v3 — 원장 기반 무손실 엔진).

이 파일은 **고정 계약(frozen contract)** 이다. 모든 모듈은 여기에 정의된
데이터 모델과 Protocol 인터페이스에 의존한다. 병렬 구현 중 이 파일은 수정하지 않는다.

설계 원칙(docs/07 참조):
  - 페이지/블록 = 책임 단위, 청크 = 작업 단위.
  - AI 출력은 자유 문장이 아니라 block_id를 보존하는 계약이다.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

# --------------------------------------------------------------------------- 열거형
BlockType = Literal[
    "title", "paragraph", "quote", "footnote", "table", "formula", "caption"
]
Status = Literal["parsed", "chunked", "polished", "verified", "failed"]
ChangeLevel = Literal["none", "light", "medium", "heavy"]
HonestMarker = Literal["star", "crescent"]  # ★ 무조건 / ◑ 주의(정직 봉인)
TaskStatus = Literal["pending", "running", "verified", "failed", "blocked"]


# --------------------------------------------------------------------------- 해시 유틸
def sha256_text(text: str) -> str:
    """텍스트의 SHA-256 16진 해시. 원장 추적·감사의 기준값."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex}"


# --------------------------------------------------------------------------- 데이터 모델
@dataclass
class Block:
    """최소 추적 단위. 모든 원문 텍스트는 블록으로 식별된다."""
    block_id: str
    page_id: str
    order_index: int
    block_type: BlockType
    text: str
    source_hash: str = ""
    polished_text: str = ""
    status: Status = "parsed"

    def __post_init__(self) -> None:
        if not self.source_hash:
            self.source_hash = sha256_text(self.text)


@dataclass
class Page:
    """책임 단위. 검증은 항상 페이지/블록 기준으로 되돌려 수행한다."""
    page_id: str
    page_number: int
    blocks: list[Block] = field(default_factory=list)
    chapter_id: str = ""
    raw_text: str = ""
    normalized_text: str = ""
    source_hash: str = ""
    output_hash: str = ""
    status: Status = "parsed"

    def __post_init__(self) -> None:
        if not self.raw_text:
            self.raw_text = "\n".join(b.text for b in self.blocks)
        if not self.source_hash:
            self.source_hash = sha256_text(self.raw_text)


@dataclass
class Chunk:
    """작업 단위. 토큰 한계 때문에 윤문 요청은 청크로 보낸다."""
    chunk_id: str
    primary_block_ids: list[str]
    overlap_block_ids: list[str] = field(default_factory=list)
    page_start: int = 0
    page_end: int = 0
    token_estimate: int = 0
    status: Status = "chunked"


@dataclass
class PolishedBlock:
    """윤문 출력 계약. 입력 block_id마다 정확히 하나가 반환되어야 한다."""
    block_id: str
    polished_text: str
    change_level: ChangeLevel = "none"
    honest_marker: HonestMarker = "star"
    warnings: list[str] = field(default_factory=list)


@dataclass
class PolishResult:
    """워커(폴리셔)의 청크 단위 출력."""
    chunk_id: str
    polished_blocks: list[PolishedBlock] = field(default_factory=list)
    chunk_summary_after: str = ""
    terminology_updates: list[dict] = field(default_factory=list)
    continuity_notes: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)


@dataclass
class StyleProfile:
    """Style Bible. 대형 원고의 문체·용어 일관성 기준."""
    sentence_length_target: int = 60
    honorific_level: str = "plain"          # plain | polite | formal
    tone: str = "neutral"
    allowed_changes: list[str] = field(default_factory=lambda: ["spacing", "typo", "flow"])
    forbidden_changes: list[str] = field(
        default_factory=lambda: [
            "number", "date", "person", "place", "citation",
            "formula", "code", "isbn", "url", "footnote_number",
        ]
    )
    genre_rules: dict = field(default_factory=dict)
    terminology_rules: dict = field(default_factory=dict)


@dataclass
class Book:
    book_id: str
    title: str = ""
    author: str = ""
    genre: str = ""
    language: str = "ko"
    source_format: str = ""
    source_hash: str = ""
    created_at: str = ""


@dataclass
class AuditEvent:
    event_id: str
    book_id: str
    target_id: str
    event_type: str
    before_hash: str = ""
    after_hash: str = ""
    payload_json: str = ""
    trace_id: str = ""
    created_at: str = ""


@dataclass
class MemoryItem:
    memory_id: str
    book_id: str
    layer: int                      # 1 정적 / 2 추출 / 3 누적
    memory_type: str                # term | character | motif | style_decision ...
    content: str
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)


@dataclass
class TaskNode:
    """CID 스케줄러의 작업 노드. 의존성 DAG로 병렬/순서를 결정한다."""
    task_id: str
    role: str
    target_id: str = ""
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = "pending"


# --------------------------------------------------------------------------- 인터페이스 계약
@runtime_checkable
class Parser(Protocol):
    """원고 파일 → 페이지 목록(블록 포함)."""
    def parse(self, source_path: str) -> list[Page]: ...


@runtime_checkable
class Polisher(Protocol):
    """청크 페이로드 → PolishResult. 입력 block_id를 모두 보존해야 한다."""
    def polish(self, payload: dict, style_bible: str = "") -> PolishResult: ...


@runtime_checkable
class Repository(Protocol):
    """파이프라인이 의존하는 저장소 계약."""
    def is_done(self, chunk_id: str) -> bool: ...
    def build_chunk_payload(self, chunk: Chunk) -> dict: ...
    def save_polished_chunk(self, chunk_id: str, result: PolishResult) -> None: ...
    def audit(self, target_id: str, result: PolishResult) -> None: ...
    def verify_book_coverage(self) -> dict: ...
    def export_all_formats(self) -> dict: ...
