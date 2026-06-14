"""커넥터 팩토리.

platform_id -> 커넥터 인스턴스 매핑. 공식 API 가 있는 플랫폼만 등록한다.
"""
from __future__ import annotations

from .base import ApiConnector
from .gumroad import GumroadConnector
from .leanpub import LeanpubConnector
from .publishdrive import PublishDriveConnector

# 공식 API 를 제공하는 플랫폼만 등록.
_CONNECTORS: dict[str, type[ApiConnector]] = {
    GumroadConnector.platform_id: GumroadConnector,
    LeanpubConnector.platform_id: LeanpubConnector,
    PublishDriveConnector.platform_id: PublishDriveConnector,
}


def get_connector(platform_id: str, token: str | None = None) -> ApiConnector | None:
    """platform_id 에 해당하는 커넥터 인스턴스. 없으면 None."""
    cls = _CONNECTORS.get(platform_id)
    if cls is None:
        return None
    return cls(token=token)


def api_platform_ids() -> list[str]:
    """공식 API 커넥터가 있는 platform_id 목록(정렬)."""
    return sorted(_CONNECTORS.keys())


def has_api(platform_id: str) -> bool:
    """해당 플랫폼에 공식 API 커넥터가 있는지."""
    return platform_id in _CONNECTORS
