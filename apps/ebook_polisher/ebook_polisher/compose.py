"""OCES 단계 1·2 — Outline(목차 설계) + Write(본문 집필) 모듈.

03-algorithms.md의 §2(Outline)·§3(Write, 캐리오버 일관성 엔진)을 구현한다.

설계 원칙:
  - 목차(skeleton)는 규칙 기반·결정적으로 생성한다(LLM 비호출). 03 §2 분량 배분.
  - 본문은 Provider.complete(stage="write")로 챕터 루프 + running summary 캐리오버(03 §3.2).
  - StubProvider 사용 시 전 과정이 결정적(같은 입력 → 같은 출력)이라 오프라인 테스트가 안정적.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ebook_polisher.llm_provider import Provider, StubProvider

# --------------------------------------------------------------------------- 프롬프트 상수 (부록 A)
OUTLINE_SYSTEM = (
    "너는 한국어 독자를 위한 해당 분야의 편집장이다. "
    "MECE(상호배타·전체포괄)한 목차를 설계하라. "
    "각 챕터에는 '무엇을·왜·어떤 순서로' 다룰지 집필 브리프를 포함하라. "
    "서론으로 시작하고 결론으로 마무리하며, 제목은 중복되지 않게 한다."
)

WRITER_SYSTEM = (
    "너는 한국어 본문 집필자다. Style Bible을 절대 준수하라. "
    "근거 없는 사실 주장은 금지하며 필요한 경우 인용 [src]을 사용한다. "
    "이전 장의 요약(앞 맥락)과 모순되지 않게 자연스럽게 이어 쓴다. "
    "목표 분량을 ±15% 범위로 맞춘다."
)

# running summary가 너무 길어지지 않도록 유지하는 한계(문자 기준). 03 §3.2 compress().
_SUMMARY_MAX_CHARS = 600
# 챕터 요약(다음 장 캐리오버)으로 보관할 최대 문자 수.
_CHAPTER_SUMMARY_CHARS = 200
# 최소 챕터 수(서론/본문/결론).
_MIN_CHAPTERS = 3


# --------------------------------------------------------------------------- 데이터 모델
@dataclass
class OutlineChapter:
    """목차의 한 챕터. 집필 전후 상태를 모두 담는다."""
    idx: int
    title: str
    brief: str
    target_words: int
    content_md: str = ""
    summary: str = ""


@dataclass
class Outline:
    """책 한 권의 목차(챕터 목록 포함)."""
    title: str
    topic: str
    language: str
    chapters: list[OutlineChapter] = field(default_factory=list)


# --------------------------------------------------------------------------- Outline (03 §2)
def build_outline(
    title: str,
    topic: str,
    n_chapters: int = 6,
    length_target: int = 6000,
    language: str = "ko",
) -> Outline:
    """규칙 기반·결정적 목차 생성(LLM 비호출).

    서론으로 시작, 결론으로 마무리, 중간 챕터는 주제 중심으로 구성한다.
    분량은 가중치(서론/결론 가볍게, 본문 무겁게)로 배분하고 length_target ±5%로 정규화한다.
    """
    n = max(_MIN_CHAPTERS, int(n_chapters))

    # --- 제목/브리프 구성 (중간 챕터를 다양한 테마로 회전시켜 중복 방지)
    middle_count = n - 2  # 서론·결론 제외
    middle_themes = [
        ("{topic}의 배경과 맥락", "{topic}이(가) 왜 중요한지 배경과 등장 맥락을 설명한다."),
        ("{topic}의 핵심 개념 {k}", "{topic}을(를) 이해하는 데 필요한 핵심 개념 {k}을(를) 정의하고 풀어낸다."),
        ("{topic}의 작동 원리", "{topic}이(가) 실제로 어떻게 작동하는지 단계별로 설명한다."),
        ("{topic}의 사례와 응용", "{topic}을(를) 적용한 구체적 사례와 응용을 다룬다."),
        ("{topic}의 도전 과제와 한계", "{topic}이(가) 직면한 도전 과제와 한계를 짚는다."),
        ("{topic}의 전망과 미래", "{topic}의 향후 전망과 발전 방향을 전망한다."),
    ]

    chapters: list[OutlineChapter] = []
    chapters.append(
        OutlineChapter(
            idx=0,
            title="서론",
            brief=f"독자에게 {topic}을(를) 소개하고, 이 책이 다룰 범위와 읽는 방법을 안내한다.",
            target_words=0,
        )
    )

    concept_k = 0
    for m in range(middle_count):
        theme_title, theme_brief = middle_themes[m % len(middle_themes)]
        if "{k}" in theme_title:
            concept_k += 1
            ttl = theme_title.format(topic=topic, k=concept_k)
            brf = theme_brief.format(topic=topic, k=concept_k)
        else:
            ttl = theme_title.format(topic=topic)
            brf = theme_brief.format(topic=topic)
        chapters.append(
            OutlineChapter(idx=m + 1, title=ttl, brief=brf, target_words=0)
        )

    chapters.append(
        OutlineChapter(
            idx=n - 1,
            title="결론",
            brief=f"{topic}에 대한 핵심 내용을 요약하고, 독자가 다음에 할 수 있는 행동을 제시한다.",
            target_words=0,
        )
    )

    # --- 제목 유일성 보장(이론상 회전으로 중복 가능 → 접미사로 구분)
    seen: dict[str, int] = {}
    for ch in chapters:
        if ch.title in seen:
            seen[ch.title] += 1
            ch.title = f"{ch.title} ({seen[ch.title]})"
        else:
            seen[ch.title] = 1

    # --- 분량 배분: 서론/결론 가볍게(가중치 1.0), 본문 무겁게(가중치 2.0)
    weights: list[float] = []
    for i in range(n):
        if i == 0 or i == n - 1:
            weights.append(1.0)
        else:
            weights.append(2.0)
    total_w = sum(weights)

    allocated = [int(round(length_target * w / total_w)) for w in weights]
    # 반올림 오차를 마지막(결론)이 아닌 가장 무거운 챕터에 흡수시켜 ±5% 보장
    diff = length_target - sum(allocated)
    if allocated:
        heaviest = max(range(n), key=lambda i: weights[i])
        allocated[heaviest] += diff

    for ch, words in zip(chapters, allocated):
        ch.target_words = max(1, words)

    return Outline(title=title, topic=topic, language=language, chapters=chapters)


# --------------------------------------------------------------------------- 압축 헬퍼 (03 §3.2)
def _compress(text: str, max_chars: int = _SUMMARY_MAX_CHARS) -> str:
    """running summary를 한계 내로 유지(뒤쪽 max_chars 보존)."""
    text = " ".join(text.split())  # 공백 정규화 → 결정적
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _chapter_summary(content_md: str, max_chars: int = _CHAPTER_SUMMARY_CHARS) -> str:
    """본문에서 다음 장으로 넘길 요약을 결정적으로 추출(앞 1~2문장 / 앞 ~max_chars자)."""
    text = " ".join(content_md.split())
    if not text:
        return ""
    # 앞 1~2문장 우선
    sentences: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in ("。", ".", "!", "?"):
            sentences.append(buf.strip())
            buf = ""
            if len(sentences) >= 2:
                break
    summary = " ".join(sentences).strip() if sentences else text
    if not summary:
        summary = text
    if len(summary) > max_chars:
        summary = summary[:max_chars]
    return summary.strip()


# --------------------------------------------------------------------------- Write (03 §3.2)
def write_book(outline: Outline, provider: Provider, style_bible: str = "") -> Outline:
    """챕터 루프 + 캐리오버로 본문을 집필한다(03 §3.2). outline을 변형해 반환.

    각 챕터마다 StubProvider가 이해하는 힌트 라인(TITLE/TOPIC/BRIEF/TARGET/CARRY)을
    포함한 user 프롬프트를 만들어 complete(stage="write")를 호출한다.
    """
    running_summary = ""
    for ch in outline.chapters:
        user = (
            f"TITLE::{ch.title}\n"
            f"TOPIC::{outline.topic}\n"
            f"BRIEF::{ch.brief}\n"
            f"TARGET::{ch.target_words}\n"
            f"CARRY::{running_summary}\n"
            f"STYLE::{style_bible}"
        )
        draft = provider.complete(
            system=WRITER_SYSTEM,
            user=user,
            stage="write",
            max_tokens=2000,
        )
        ch.content_md = draft
        ch.summary = _chapter_summary(draft)
        running_summary = _compress(running_summary + " " + ch.summary)
    return outline


# --------------------------------------------------------------------------- 조립
def compose_to_markdown(
    title: str,
    topic: str,
    provider: Provider | None = None,
    n_chapters: int = 6,
    length_target: int = 6000,
    language: str = "ko",
    style_bible: str = "",
) -> str:
    """제목+주제 → 단일 Markdown 원고. provider 기본값은 StubProvider()."""
    if provider is None:
        provider = StubProvider()
    outline = build_outline(
        title=title,
        topic=topic,
        n_chapters=n_chapters,
        length_target=length_target,
        language=language,
    )
    outline = write_book(outline, provider, style_bible=style_bible)

    parts = [f"# {title}\n\n"]
    for ch in outline.chapters:
        parts.append(f"## {ch.title}\n\n{ch.content_md}\n\n")
    return "".join(parts)
