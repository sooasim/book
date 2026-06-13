"""플랫폼별 입력칸 선택자(FieldSelector) 매핑 저장소.

매핑은 학습/보정되어 JSON 으로 저장된다(플랫폼당 한 파일).
순수/결정적 함수로 구성하며 표준 라이브러리(json, pathlib)만 사용한다.
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import FieldSelector

# 매핑 JSON 이 저장되는 기본 디렉터리.
MAPPINGS_DIR = Path(__file__).resolve().parents[0] / "mappings"

# 게시 폼에서 흔히 채워야 하는 기본 필드 키.
DEFAULT_FIELD_KEYS = (
    "title",
    "subtitle",
    "author",
    "description",
    "keywords",
    "categories",
    "price",
    "language",
    "manuscript_file",
    "cover_file",
    "isbn",
)


def _selector_to_dict(sel: FieldSelector) -> dict:
    """FieldSelector -> 저장용 dict(field_key 는 JSON 키로 별도 사용)."""
    return {"by": sel.by, "selector": sel.selector, "field_type": sel.field_type}


def _selector_from_dict(field_key: str, data: dict) -> FieldSelector:
    """저장된 dict -> FieldSelector."""
    return FieldSelector(
        field_key=field_key,
        by=data["by"],
        selector=data["selector"],
        field_type=data.get("field_type", "text"),
    )


class MappingStore:
    """플랫폼별 FieldSelector 매핑의 JSON 영속 저장소."""

    def __init__(self, mappings_dir=None):
        self.mappings_dir = Path(mappings_dir) if mappings_dir is not None else MAPPINGS_DIR

    def path_for(self, platform_id: str) -> Path:
        """플랫폼의 매핑 JSON 경로."""
        return self.mappings_dir / f"{platform_id}.json"

    def load(self, platform_id: str) -> dict:
        """매핑 JSON 을 읽어 {field_key: FieldSelector} 로 반환. 파일 없으면 {}."""
        path = self.path_for(platform_id)
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {
            field_key: _selector_from_dict(field_key, data)
            for field_key, data in raw.items()
        }

    def save(self, platform_id: str, selectors: dict) -> str:
        """{field_key: FieldSelector} 를 JSON 으로 저장하고 경로를 문자열로 반환."""
        self.mappings_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(platform_id)
        payload = {
            field_key: _selector_to_dict(sel) for field_key, sel in selectors.items()
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return str(path)

    def set_field(
        self,
        platform_id: str,
        field_key: str,
        by: str,
        selector: str,
        field_type: str = "text",
    ) -> str:
        """필드 선택자를 추가/갱신(학습)하고 저장한다. 저장 경로를 반환."""
        selectors = self.load(platform_id)
        selectors[field_key] = FieldSelector(
            field_key=field_key, by=by, selector=selector, field_type=field_type
        )
        return self.save(platform_id, selectors)

    def resolve(self, platform_id: str, field_key: str):
        """주어진 필드 키의 FieldSelector 를 반환. 없으면 None."""
        return self.load(platform_id).get(field_key)


def coverage(platform_id: str, store: MappingStore) -> dict:
    """플랫폼 매핑의 기본 필드 커버리지를 반환.

    {"known": [존재하는 field_key], "missing": [없는 DEFAULT_FIELD_KEYS]}.
    """
    selectors = store.load(platform_id)
    known = [k for k in selectors]
    missing = [k for k in DEFAULT_FIELD_KEYS if k not in selectors]
    return {"known": known, "missing": missing}


def seed_example(store: MappingStore) -> str:
    """amazon_kdp 용 예시 매핑을 저장한다(플레이스홀더, 사용자가 보정).

    실제 동작 보장이 아닌 형식 예시이며, 일반적인 선택자를 사용한다.
    저장 경로를 반환한다.
    """
    selectors = {
        "title": FieldSelector("title", "name", "title", "text"),
        "subtitle": FieldSelector("subtitle", "name", "subtitle", "text"),
        "author": FieldSelector("author", "name", "author", "text"),
        "description": FieldSelector("description", "css", "#description", "textarea"),
        "keywords": FieldSelector("keywords", "name", "keywords", "text"),
        "price": FieldSelector("price", "name", "price", "text"),
        "manuscript_file": FieldSelector(
            "manuscript_file", "css", "input[type=file].manuscript", "file"
        ),
        "cover_file": FieldSelector(
            "cover_file", "css", "input[type=file].cover", "file"
        ),
    }
    return store.save("amazon_kdp", selectors)
