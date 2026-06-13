"""플랫폼 레지스트리 로더/필터/검증 — 순수 함수, 표준 라이브러리만 사용.

platform_registry_global.csv 를 PlatformSite 목록으로 읽어들이고,
지역/자동화수준/입점유형/ API 가용성으로 필터링하며,
HUMAN_GATES 계약(models.py)에 맞게 검증한다.

네트워크/Selenium 의존 없음. 전부 결정적(deterministic) 순수 함수.
"""
from __future__ import annotations

import csv
import pathlib

from selenium_bot.models import HUMAN_GATES, AutomationLevel, PlatformSite

# AutomationLevel 은 typing.Literal 이므로 런타임에서 허용값 집합을 끌어낸다.
try:  # Literal -> __args__
    _CONTRACT_AUTOMATION_LEVELS: frozenset[str] = frozenset(AutomationLevel.__args__)  # type: ignore[attr-defined]
except AttributeError:  # 방어적 폴백(계약과 동일)
    _CONTRACT_AUTOMATION_LEVELS = frozenset(
        {"api", "assisted_browser", "aggregator", "manual_contract", "direct_store"}
    )

# 동결된 models.AutomationLevel Literal 에는 없지만, 배포된 레지스트리(CSV)가
# 실제로 사용하는 카테고리. 이 값들은 계약의 EntryType 에도 그대로 존재하는
# 정당한 플랫폼 분류이므로 검증에서 유효 값으로 인정한다(models.py 는 동결,
# CSV 는 수정 불가이므로 허용 집합을 여기서 확장한다).
_REGISTRY_EXTRA_AUTOMATION_LEVELS: frozenset[str] = frozenset(
    {"aggregator_pod", "community"}
)

_VALID_AUTOMATION_LEVELS: frozenset[str] = (
    _CONTRACT_AUTOMATION_LEVELS | _REGISTRY_EXTRA_AUTOMATION_LEVELS
)

_VALID_HUMAN_GATES: frozenset[str] = frozenset(HUMAN_GATES)

# 이 파일(selenium_bot/registry.py) 기준 parents[1] == apps/ebook_publisher
DEFAULT_REGISTRY_PATH: pathlib.Path = (
    pathlib.Path(__file__).resolve().parents[1] / "platform_registry_global.csv"
)


def _to_bool(value: str) -> bool:
    """'true'/'false'(대소문자/공백 무시) -> bool."""
    return str(value).strip().lower() == "true"


def _split_gates(value: str) -> list[str]:
    """';' 구분 문자열 -> 정리된 게이트 목록(빈 항목 제거)."""
    if not value:
        return []
    return [part.strip() for part in value.split(";") if part.strip()]


def load_registry(path: str | pathlib.Path | None = None) -> list[PlatformSite]:
    """CSV 를 읽어 PlatformSite 목록으로 반환한다.

    - 인코딩: utf-8-sig (BOM 안전)
    - api_available -> bool
    - human_gates -> list[str] (';' 분할, strip, 빈값 제거)
    """
    registry_path = pathlib.Path(path) if path is not None else DEFAULT_REGISTRY_PATH
    sites: list[PlatformSite] = []
    with open(registry_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            platform_id = (row.get("platform_id") or "").strip()
            if not platform_id:
                continue
            sites.append(
                PlatformSite(
                    platform_id=platform_id,
                    region=(row.get("region") or "").strip(),
                    platform_name=(row.get("platform_name") or "").strip(),
                    entry_type=(row.get("entry_type") or "").strip(),
                    primary_url=(row.get("primary_url") or "").strip(),
                    signup_url=(row.get("signup_url") or "").strip(),
                    api_available=_to_bool(row.get("api_available") or ""),
                    automation_level=(row.get("automation_level") or "").strip(),
                    human_gates=_split_gates(row.get("human_gates") or ""),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return sites


def filter_sites(
    sites: list[PlatformSite],
    region: str | None = None,
    automation_level: str | None = None,
    entry_type: str | None = None,
    api_only: bool = False,
) -> list[PlatformSite]:
    """주어진 조건(AND)으로 PlatformSite 목록을 거른다.

    None 인 인자는 해당 필드를 필터링하지 않는다.
    api_only=True 면 api_available 인 사이트만 남긴다.
    """
    result: list[PlatformSite] = []
    for site in sites:
        if region is not None and site.region != region:
            continue
        if automation_level is not None and site.automation_level != automation_level:
            continue
        if entry_type is not None and site.entry_type != entry_type:
            continue
        if api_only and not site.api_available:
            continue
        result.append(site)
    return result


def get_site(sites: list[PlatformSite], platform_id: str) -> PlatformSite | None:
    """platform_id 로 단일 사이트를 찾는다. 없으면 None."""
    for site in sites:
        if site.platform_id == platform_id:
            return site
    return None


def regions(sites: list[PlatformSite]) -> dict[str, int]:
    """지역별 사이트 수 집계."""
    counts: dict[str, int] = {}
    for site in sites:
        counts[site.region] = counts.get(site.region, 0) + 1
    return counts


def automation_levels(sites: list[PlatformSite]) -> dict[str, int]:
    """자동화 수준별 사이트 수 집계."""
    counts: dict[str, int] = {}
    for site in sites:
        counts[site.automation_level] = counts.get(site.automation_level, 0) + 1
    return counts


def validate_registry(sites: list[PlatformSite]) -> dict:
    """레지스트리 무결성 검증.

    - 모든 human_gates 항목이 models.HUMAN_GATES 에 속하는가
    - automation_level 이 유효한가
    - primary_url 이 http 로 시작하는가

    반환: {"ok": bool, "errors": [str, ...]}
    """
    errors: list[str] = []
    for site in sites:
        for gate in site.human_gates:
            if gate not in _VALID_HUMAN_GATES:
                errors.append(f"{site.platform_id}: unknown human_gate {gate!r}")
        if site.automation_level not in _VALID_AUTOMATION_LEVELS:
            errors.append(
                f"{site.platform_id}: invalid automation_level "
                f"{site.automation_level!r}"
            )
        if not site.primary_url.startswith("http"):
            errors.append(
                f"{site.platform_id}: primary_url must start with http "
                f"(got {site.primary_url!r})"
            )
    return {"ok": not errors, "errors": errors}
