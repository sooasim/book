"""Leanpub API 커넥터.

Leanpub API 는 기능이 제한적이라 페이로드는 예시(illustrative) 성격이다.
"""
from __future__ import annotations

from .base import ApiConnector


class LeanpubConnector(ApiConnector):
    platform_id = "leanpub"
    token_env = "LEANPUB_API_KEY"

    def endpoint(self) -> str:
        return "https://leanpub.com/api"

    def build_payload(self, book: dict, files: dict | None = None) -> dict:
        book = book or {}
        return {
            "title": book.get("title", ""),
            "subtitle": book.get("subtitle", ""),
            "about_the_book": book.get("description", ""),
        }
