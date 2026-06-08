"""텍스트 정규화 모듈.

결정론적(deterministic)·순수(pure) 함수만 둔다. 같은 입력이면 언제나 같은 출력이며,
정규화는 멱등(idempotent)이다: normalize_text(normalize_text(x)) == normalize_text(x).

원칙:
  - 숫자/글자/문장부호의 '내용'은 절대 바꾸지 않는다(공백/제어문자만 정돈).
  - 작은 순수 함수로 분리해 조합한다.
"""
from __future__ import annotations

import unicodedata

# 제거 대상 제로폭(zero-width)·BOM 계열 문자.
#   U+200B ZERO WIDTH SPACE
#   U+200C ZERO WIDTH NON-JOINER
#   U+200D ZERO WIDTH JOINER
#   U+2060 WORD JOINER
#   U+FEFF ZERO WIDTH NO-BREAK SPACE (BOM)
_ZERO_WIDTH_CHARS = (
    "​",
    "‌",
    "‍",
    "⁠",
    "﻿",
)


def strip_invisible(text: str) -> str:
    """제로폭·BOM 등 보이지 않는 문자를 제거한다. 순수 함수."""
    for ch in _ZERO_WIDTH_CHARS:
        text = text.replace(ch, "")
    return text


def _collapse_spaces(line: str) -> str:
    """한 줄 내 연속 공백(space)을 하나로 축약한다. 줄바꿈은 다루지 않는다."""
    result = []
    prev_space = False
    for ch in line:
        if ch == " ":
            if not prev_space:
                result.append(ch)
            prev_space = True
        else:
            result.append(ch)
            prev_space = False
    return "".join(result)


def _collapse_blank_lines(lines: list[str]) -> list[str]:
    """3줄 이상 연속 빈 줄을 최대 2줄로 줄인다."""
    result: list[str] = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run <= 2:
                result.append(line)
        else:
            blank_run = 0
            result.append(line)
    return result


def normalize_text(text: str) -> str:
    """텍스트를 결정론적으로 정규화한다.

    순서:
      1) 유니코드 NFC 정규화
      2) 제로폭/BOM 제거
      3) 탭 -> 공백 치환
      4) 줄 단위로 연속 공백 축약 + 우측 공백 제거
      5) 3줄 이상 빈 줄을 최대 2줄로 축약

    숫자/글자/문장부호 내용은 보존된다. 멱등하다.
    """
    if not text:
        return ""

    # 1) NFC 정규화 (예: 분해된 한글 자모 -> 완성형)
    text = unicodedata.normalize("NFC", text)

    # 2) 보이지 않는 문자 제거
    text = strip_invisible(text)

    # 3) 탭을 공백으로
    text = text.replace("\t", " ")

    # 줄바꿈 표준화 (\r\n, \r -> \n) 후 줄 단위 처리
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    # 4) 줄별 공백 축약 + 우측 공백 제거
    lines = [_collapse_spaces(line).rstrip(" ") for line in lines]

    # 5) 빈 줄 축약
    lines = _collapse_blank_lines(lines)

    return "\n".join(lines)
