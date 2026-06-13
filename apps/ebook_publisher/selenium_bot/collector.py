"""레지스트리 프로버(prober) — 사이트 도달성/가입 링크 점검.

설계:
  - probe_plan / summarize_probe / normalize_url / write_report 는 전부 순수 함수.
    네트워크/Selenium 없이 결정적으로 동작하며 테스트 대상이다.
  - probe_sites 만 실제 브라우저(Selenium WebDriver, 덕 타이핑)를 사용한다.
    driver 가 None 이면 RuntimeError 를 던지고, 오프라인에서는 probe_plan 을 쓴다.
  - selenium 은 절대 모듈 최상단에서 import 하지 않는다(미설치 환경에서도 import 가능).
"""
from __future__ import annotations

import json
import pathlib
from urllib.parse import urlparse, urlunparse

from selenium_bot.models import PlatformSite

# 페이지 본문에서 가입 링크 존재를 추정할 때 찾는 토큰(영/한).
_SIGNUP_TOKENS: tuple[str, ...] = ("sign up", "register", "signup", "가입")


def normalize_url(url: str) -> str:
    """URL 을 정규화한다.

    - 앞뒤 공백 제거
    - 스킴이 없으면 https:// 를 붙인다
    빈 문자열은 그대로 빈 문자열로 둔다.
    """
    cleaned = (url or "").strip()
    if not cleaned:
        return ""
    parsed = urlparse(cleaned)
    if not parsed.scheme:
        # 스킴 없는 'example.com/path' 형태 -> https 부여 후 재파싱
        parsed = urlparse("https://" + cleaned)
    return urlunparse(parsed)


def probe_plan(sites: list[PlatformSite]) -> list[dict]:
    """실제 프로브가 채울 결정적 계획을 만든다(순수 함수).

    각 사이트당 한 건. None 은 '아직 점검 안 됨'을 뜻한다.
    """
    plan: list[dict] = []
    for site in sites:
        plan.append(
            {
                "platform_id": site.platform_id,
                "primary_url": site.primary_url,
                "signup_url": site.signup_url,
                "reachable": None,
                "title": None,
                "has_signup_link": None,
            }
        )
    return plan


def summarize_probe(results: list[dict]) -> dict:
    """프로브 결과의 reachable 상태를 집계한다.

    반환: {"total", "reachable_true", "reachable_false", "reachable_none"}
    """
    summary = {
        "total": len(results),
        "reachable_true": 0,
        "reachable_false": 0,
        "reachable_none": 0,
    }
    for item in results:
        reachable = item.get("reachable")
        if reachable is True:
            summary["reachable_true"] += 1
        elif reachable is False:
            summary["reachable_false"] += 1
        else:
            summary["reachable_none"] += 1
    return summary


def _detect_signup_link(page_source: str) -> bool:
    """페이지 본문에 가입 관련 토큰이 있는지 검사한다."""
    haystack = (page_source or "").lower()
    return any(token in haystack for token in _SIGNUP_TOKENS)


def probe_sites(sites: list[PlatformSite], driver=None) -> list[dict]:
    """실제 브라우저로 각 사이트의 primary_url 을 방문해 결과를 채운다.

    driver 가 None 이면 RuntimeError(오프라인에서는 probe_plan 사용).
    driver 는 덕 타이핑: .get(url) 메서드, .title 속성, .page_source 속성을 가진다.
    예외 발생 시 해당 사이트는 reachable=False 로 기록한다.

    selenium 을 import 하지 않으므로 미설치 환경에서도 이 모듈은 import 된다.
    """
    if driver is None:
        raise RuntimeError(
            "Selenium driver required for live probing; use probe_plan for offline."
        )

    results = probe_plan(sites)
    for item in results:
        url = normalize_url(item["primary_url"])
        try:
            driver.get(url)
            item["reachable"] = True
            item["title"] = driver.title
            item["has_signup_link"] = _detect_signup_link(driver.page_source)
        except Exception:  # noqa: BLE001 - 어떤 드라이버 오류든 도달 실패로 기록
            item["reachable"] = False
            item["title"] = None
            item["has_signup_link"] = None
    return results


def write_report(results: list[dict], path: str | pathlib.Path) -> str:
    """프로브 결과를 JSON 으로 기록하고 경로(str)를 반환한다."""
    out_path = pathlib.Path(path)
    payload = {
        "summary": summarize_probe(results),
        "results": results,
    }
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return str(out_path)
