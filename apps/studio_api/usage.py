"""OneClick eBook Studio — 사용량/비용 추적 + 경량 유저 스코핑 (순수 stdlib).

멀티테넌시와 사용량/비용 대시보드의 씨앗(OCES 02 §7, 04 §5).

유저는 문자열 ``user_id`` 로 식별한다(미인증 시 기본값 ``"public"``). 유저별로
토큰 사용량과 생성한 책 수를 누적하고, 선택적 토큰 쿼터를 강제하며, 대시보드용
집계 통계를 노출한다.

설계 원칙:
- 결정적(deterministic): 스레드 실행 순서에 의존하지 않는다. 누적은 교환법칙이
  성립하므로 동시 ``record`` 호출의 합은 항상 동일하다.
- 스레드 안전(thread-safe): 모든 저장소 변경은 단일 ``threading.Lock`` 으로
  직렬화한다.
"""
from __future__ import annotations

import threading
from typing import Dict

# 미인증 유저의 기본 스코프 식별자.
DEFAULT_USER = "public"

# 신규 유저에게 부여되는 기본 토큰 쿼터.
DEFAULT_TOKEN_QUOTA = 2_000_000


def estimate_tokens(text: str) -> int:
    """텍스트의 토큰 수를 어림한다(엔진 휴리스틱과 일치: 글자수//2)."""
    return max(0, len(text) // 2)


class UsageTracker:
    """유저별 토큰/책 사용량과 쿼터를 추적하는 스레드 안전 저장소.

    내부 상태는 ``user_id -> {"tokens": int, "books": int, "quota": int}`` 형태의
    딕셔너리이며, 모든 접근은 단일 Lock 으로 직렬화된다. 외부로 반환되는 사용량
    딕셔너리는 항상 *복사본* 이므로 호출자가 내부 상태를 변경할 수 없다.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users: Dict[str, Dict[str, int]] = {}

    @staticmethod
    def _default(quota: int = DEFAULT_TOKEN_QUOTA) -> Dict[str, int]:
        return {"tokens": 0, "books": 0, "quota": quota}

    def _ensure(self, user_id: str) -> Dict[str, int]:
        """Lock 이 잡힌 상태에서 호출: 유저를 lazily 생성하고 내부 dict 반환."""
        u = self._users.get(user_id)
        if u is None:
            u = self._default()
            self._users[user_id] = u
        return u

    def record(self, user_id: str, tokens: int = 0, books: int = 0) -> dict:
        """토큰/책 사용량을 누적한다. 유저가 없으면 기본 쿼터로 생성.

        해당 유저의 현재 사용량 딕셔너리 *복사본* 을 반환한다.
        """
        with self._lock:
            u = self._ensure(user_id)
            u["tokens"] += tokens
            u["books"] += books
            return dict(u)

    def get(self, user_id: str) -> dict:
        """유저의 사용량 복사본을 반환한다. 없으면 0 + 기본 쿼터 복사본."""
        with self._lock:
            u = self._users.get(user_id)
            if u is None:
                return self._default()
            return dict(u)

    def set_quota(self, user_id: str, quota: int) -> None:
        """유저의 토큰 쿼터를 설정한다(없으면 lazily 생성)."""
        with self._lock:
            u = self._ensure(user_id)
            u["quota"] = quota

    def remaining(self, user_id: str) -> int:
        """남은 토큰 수(quota - tokens)를 반환한다.

        쿼터를 초과한 경우 음수가 될 수 있으며 클램프하지 않는다(호출자가 음수로
        초과량을 판단할 수 있도록). 클램프된 값이 필요하면 ``max(0, ...)`` 사용.
        """
        with self._lock:
            u = self._users.get(user_id)
            if u is None:
                return DEFAULT_TOKEN_QUOTA
            return u["quota"] - u["tokens"]

    def over_quota(self, user_id: str) -> bool:
        """사용 토큰이 쿼터 이상이면 True."""
        with self._lock:
            u = self._users.get(user_id)
            if u is None:
                return False
            return u["tokens"] >= u["quota"]

    def all(self) -> dict:
        """대시보드용: {user_id: 사용량_복사본} 전체 매핑."""
        with self._lock:
            return {uid: dict(u) for uid, u in self._users.items()}

    def summary(self) -> dict:
        """전체 집계: 유저 수, 총 토큰, 총 책 수."""
        with self._lock:
            total_tokens = sum(u["tokens"] for u in self._users.values())
            total_books = sum(u["books"] for u in self._users.values())
            return {
                "users": len(self._users),
                "total_tokens": total_tokens,
                "total_books": total_books,
            }

    def reset(self) -> None:
        """모든 사용량 상태를 비운다."""
        with self._lock:
            self._users.clear()


# 앱이 import 해서 공유하는 모듈 레벨 싱글턴.
tracker = UsageTracker()
