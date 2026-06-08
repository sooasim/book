"""Style Bible 생성·렌더링.

원고 윤문의 문체·용어 일관성 기준을 StyleProfile 로 구성하고,
이를 프롬프트에 끼워넣을 수 있는 사람이 읽을 수 있는 한국어 텍스트 블록으로
렌더링한다.
"""
from __future__ import annotations

from ebook_polisher.models import StyleProfile

_HONORIFIC_LABELS = {
    "plain": "평어체 (해라체)",
    "polite": "경어체 (해요체)",
    "formal": "격식체 (합쇼체)",
}


def build_style_profile(
    genre: str = "",
    honorific: str = "plain",
    sample_text: str = "",
) -> StyleProfile:
    """장르·경어 수준·표본 텍스트로부터 StyleProfile 을 구성한다."""
    if honorific not in _HONORIFIC_LABELS:
        honorific = "plain"

    profile = StyleProfile(honorific_level=honorific)

    if genre:
        profile.genre_rules = {"genre": genre}

    # 표본 텍스트가 있으면 평균 문장 길이를 추정해 목표값을 잡는다.
    if sample_text:
        sentences = [
            s for s in _split_sentences(sample_text) if s.strip()
        ]
        if sentences:
            avg = sum(len(s) for s in sentences) // len(sentences)
            # 합리적인 범위로 클램프.
            profile.sentence_length_target = max(20, min(120, avg))

    return profile


def _split_sentences(text: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    for ch in text:
        cur.append(ch)
        if ch in ".!?。\n":
            out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out


def render_style_bible(profile: StyleProfile) -> str:
    """StyleProfile 을 사람이 읽을 수 있는 한국어 텍스트 블록으로 렌더링한다."""
    honorific = _HONORIFIC_LABELS.get(profile.honorific_level, profile.honorific_level)
    genre = profile.genre_rules.get("genre", "미지정") if profile.genre_rules else "미지정"

    lines = [
        "[스타일 바이블]",
        f"- 장르: {genre}",
        f"- 경어 수준: {honorific}",
        f"- 어조: {profile.tone}",
        f"- 목표 문장 길이: 약 {profile.sentence_length_target}자",
        f"- 허용 변경: {', '.join(profile.allowed_changes)}",
        f"- 금지 변경: {', '.join(profile.forbidden_changes)}",
    ]

    if profile.terminology_rules:
        terms = ", ".join(f"{k}→{v}" for k, v in profile.terminology_rules.items())
        lines.append(f"- 용어 규칙: {terms}")

    return "\n".join(lines)
