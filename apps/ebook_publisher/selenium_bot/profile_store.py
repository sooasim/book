"""기본정보 1회 입력 → 모든 곳 자동 입력 + 플랫폼별 세션(자동 로그인 유지).

- BookProfile(기본 책 정보)와 PublisherProfile(발행자 정보)를 한 번만 입력해 JSON 으로 보관.
  이후 모든 플랫폼 게시/가입 계획이 이 단일 소스를 사용한다.
- 플랫폼별 Chrome user-data-dir 을 분리 보관 → 한 번 로그인하면 세션이 유지되어
  다음 실행부터는 로그인 단계를 건너뛰고 바로 폼 자동 채움이 가능하다.

민감정보(비밀번호/세금/계좌/주민·사업자번호)는 저장하지 않는다. 그것들은 브라우저
세션(프로필 디렉터리)과 사람 입력에만 머문다.
"""
from __future__ import annotations

import json
from pathlib import Path

# 기본정보(한 번 입력하면 모든 플랫폼에 자동 적용되는 정규 책 메타데이터)
BOOK_FIELDS = (
    "book_id", "title", "subtitle", "author", "pen_name", "language",
    "description", "short_description", "keywords", "categories",
    "price_usd", "price_krw", "isbn_ebook", "age_rating", "ai_disclosure",
)
PUBLISHER_FIELDS = ("display_name", "email", "pen_name", "country", "publisher_name")

DEFAULT_BASE = Path.home() / ".oces_publisher"


def _base(base: str | None = None) -> Path:
    p = Path(base) if base else DEFAULT_BASE
    p.mkdir(parents=True, exist_ok=True)
    return p


def book_profile_path(base: str | None = None) -> Path:
    return _base(base) / "book_profile.json"


def publisher_profile_path(base: str | None = None) -> Path:
    return _base(base) / "publisher_profile.json"


def save_book_profile(data: dict, base: str | None = None) -> str:
    clean = {k: data[k] for k in BOOK_FIELDS if k in data}
    path = book_profile_path(base)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def load_book_profile(base: str | None = None) -> dict:
    path = book_profile_path(base)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_publisher_profile(data: dict, base: str | None = None) -> str:
    clean = {k: data[k] for k in PUBLISHER_FIELDS if k in data}
    path = publisher_profile_path(base)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def load_publisher_profile(base: str | None = None) -> dict:
    path = publisher_profile_path(base)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def profile_dir_for(platform_id: str, base: str | None = None) -> str:
    """플랫폼별 Chrome 영속 프로필 경로. 한 번 로그인하면 세션이 유지된다(자동 로그인)."""
    d = _base(base) / "sessions" / platform_id
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def to_book_dict(profile: dict) -> dict:
    """저장된 기본정보를 build_publish_plan 이 쓰는 book dict 로 변환(그대로 전달 가능)."""
    return dict(profile)


def is_logged_in(platform_id: str, base: str | None = None) -> bool:
    """세션 프로필이 이미 만들어져 있으면 '로그인된 적 있음'으로 본다(휴리스틱).

    실제 로그인 유효성은 페이지 접근으로 확인해야 하지만, 프로필 존재 여부로
    '처음/재방문'을 구분해 UX(로그인 단계 안내 생략)에 활용한다.
    """
    d = _base(base) / "sessions" / platform_id
    return d.exists() and any(d.iterdir())
