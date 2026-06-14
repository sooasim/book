"""API 커넥터 베이스 클래스.

설계:
  - build_payload / dry_run 은 결정적이며 네트워크를 절대 사용하지 않는다.
  - publish 만 네트워크를 사용할 수 있다(토큰 + requests 가 모두 있을 때).
  - 토큰이 없으면 publish 는 즉시 안전 실패한다(missing_token).
  - requests 가 없으면 publish 는 안전 실패한다(requests_not_installed).
  - API 경로라도 가격/세금/권리/AI 고지는 사람(출판자) 책임으로 남는다.
"""
from __future__ import annotations

import os


class ApiConnector:
    """공식 API 커넥터 베이스. 서브클래스가 plaform 스키마로 오버라이드한다."""

    platform_id: str = ""
    token_env: str = ""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.environ.get(self.token_env, "")

    # ------------------------------------------------------------------ 엔드포인트
    def endpoint(self) -> str:
        """플랫폼 API 엔드포인트 URL."""
        return ""

    # ------------------------------------------------------------------ 페이로드
    def build_payload(self, book: dict, files: dict | None = None) -> dict:
        """book -> API 페이로드(dict). 결정적, 네트워크 없음.

        베이스는 일반적인 형태를 반환한다. 서브클래스가 플랫폼 스키마로 오버라이드.
        """
        book = book or {}
        return {
            "title": book.get("title", ""),
            "description": book.get("description", ""),
            "price": book.get("price_usd", book.get("price", "")),
            "language": book.get("language", "en"),
        }

    # ------------------------------------------------------------------ dry-run
    def dry_run(self, book: dict, files: dict | None = None) -> dict:
        """네트워크 없이 페이로드와 대상 엔드포인트를 검증용으로 반환."""
        return {
            "ok": True,
            "platform": self.platform_id,
            "mode": "dry_run",
            "endpoint": self.endpoint(),
            "payload": self.build_payload(book, files),
        }

    # ------------------------------------------------------------------ publish
    def publish(self, book: dict, files: dict | None = None) -> dict:
        """실제 게시. 네트워크를 사용할 수 있는 유일한 메서드.

        토큰/requests 가 없으면 안전 실패한다. (테스트는 이 분기를 타지 않는다.)
        """
        if not self.token:
            return {"ok": False, "reason": "missing_token", "token_env": self.token_env}
        try:
            import requests  # type: ignore  # noqa: F401
        except Exception:
            return {"ok": False, "reason": "requests_not_installed"}

        payload = self.build_payload(book, files)
        headers = {"Authorization": "Bearer %s" % self.token}
        try:
            resp = requests.post(self.endpoint(), data=payload, headers=headers, timeout=30)
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            return {
                "ok": 200 <= resp.status_code < 300,
                "status_code": resp.status_code,
                "response": body,
            }
        except Exception as e:  # noqa: BLE001  네트워크 오류 래핑
            return {"ok": False, "reason": "network_error", "error": str(e)}

    # ------------------------------------------------------------------ 사람 책임
    def human_review_note(self) -> str:
        """API 경유여도 가격/세금/권리/AI 고지는 출판자 책임임을 상기."""
        return (
            "API 경로로 게시하더라도 가격/통화, 세금 정보, 저작권/출판권, "
            "AI 생성·보조 콘텐츠 고지(AI disclosure)는 여전히 출판자(사람)의 "
            "책임입니다. 게시 전 반드시 직접 확인하세요."
        )
