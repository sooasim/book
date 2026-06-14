"""Gumroad 공식 API 커넥터.

Gumroad 는 access_token + multipart 업로드를 사용한다. dry_run 은 dict 만 빌드한다.
"""
from __future__ import annotations

from .base import ApiConnector


class GumroadConnector(ApiConnector):
    platform_id = "gumroad"
    token_env = "GUMROAD_ACCESS_TOKEN"

    def endpoint(self) -> str:
        return "https://api.gumroad.com/v2/products"

    def build_payload(self, book: dict, files: dict | None = None) -> dict:
        book = book or {}
        price_raw = book.get("price_usd", book.get("price", 0))
        try:
            cents = int(round(float(price_raw or 0) * 100))
        except (TypeError, ValueError):
            cents = 0
        return {
            "name": book.get("title", ""),
            "description": book.get("description", ""),
            "price": cents,
            "url": book.get("url", ""),
        }
