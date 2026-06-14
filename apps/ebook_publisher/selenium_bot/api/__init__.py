"""공식 API 게시 커넥터 레이어.

목적: 공식 API 가 있는 플랫폼은 브라우저 자동화 대신 API 경로(ToS 친화적,
automation level "api")를 우선한다. 페이로드 빌드와 dry_run 은 네트워크 없이
표준 라이브러리만으로 동작한다. 실제 네트워크(requests)는 선택 사항이며
publish() 에서만 사용한다.
"""
from __future__ import annotations

from .base import ApiConnector
from .gumroad import GumroadConnector
from .leanpub import LeanpubConnector
from .publishdrive import PublishDriveConnector
from .factory import get_connector, api_platform_ids, has_api

__all__ = [
    "ApiConnector",
    "GumroadConnector",
    "LeanpubConnector",
    "PublishDriveConnector",
    "get_connector",
    "api_platform_ids",
    "has_api",
]
