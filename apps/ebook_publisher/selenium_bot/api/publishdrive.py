"""PublishDrive 공식 API 커넥터(배급사 경유 일괄 게시)."""
from __future__ import annotations

from .base import ApiConnector


class PublishDriveConnector(ApiConnector):
    platform_id = "publishdrive"
    token_env = "PUBLISHDRIVE_API_KEY"

    def endpoint(self) -> str:
        return "https://api.publishdrive.com/v1/books"

    def build_payload(self, book: dict, files: dict | None = None) -> dict:
        book = book or {}
        return {
            "title": book.get("title", ""),
            "description": book.get("description", ""),
            "isbn": book.get("isbn_ebook", ""),
            "language": book.get("language", "en"),
            "price_usd": book.get("price_usd", book.get("price", "")),
        }
