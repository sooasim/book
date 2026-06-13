"""Selenium WebDriver 팩토리 (로컬 PC 실행 전용, 선택적 의존성).

selenium 이 설치되어 있을 때만 동작한다. 코어 로직/테스트는 이 모듈을 import 하지 않거나
driver=None 로 동작하므로, selenium 미설치 환경(CI/컨테이너)에서도 전체 테스트가 통과한다.

영속 프로필(user-data-dir)을 사용해 사용자가 한 번 로그인하면 세션이 유지된다.
비밀번호/세션 토큰은 우리 코드가 다루지 않고 브라우저 프로필에만 보관된다.
"""
from __future__ import annotations

from pathlib import Path


def selenium_available() -> bool:
    try:
        import selenium  # noqa: F401
        return True
    except Exception:
        return False


def make_chrome(profile_dir: str | None = None, headless: bool = False,
                window_size: str = "1280,1000"):
    """Chrome WebDriver 생성. selenium + 드라이버가 필요.

    profile_dir: 로그인 세션을 보존할 사용자 데이터 디렉터리(권장).
    headless: 가입/게시 보조는 사람이 봐야 하므로 기본 False(헤드리스 비권장).
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except Exception as exc:  # pragma: no cover - 의존성 없을 때
        raise RuntimeError(
            "selenium 이 필요합니다. 로컬에서: pip install -r selenium_bot/requirements-selenium.txt"
        ) from exc

    options = Options()
    if profile_dir:
        Path(profile_dir).mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir}")
    if headless:
        options.add_argument("--headless=new")
    options.add_argument(f"--window-size={window_size}")
    # 자동화 표시 최소화는 하지 않는다(탐지 회피 목적의 stealth 옵션 미사용).

    # 드라이버 경로: webdriver-manager 가 있으면 자동, 없으면 PATH 의 chromedriver.
    try:
        from selenium.webdriver.chrome.service import Service
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        except Exception:
            service = Service()  # PATH 의 chromedriver 사용
        return webdriver.Chrome(service=service, options=options)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Chrome WebDriver 생성 실패: {exc}") from exc


# 매핑 by -> selenium By 문자열 (selenium 의 By 상수와 동일한 표준 문자열이라
# selenium 을 import 하지 않고도 동작하며, 실제 selenium find_element 도 이 문자열을 받는다).
def by_method(by: str) -> str:
    return {
        "css": "css selector",
        "xpath": "xpath",
        "id": "id",
        "name": "name",
    }.get(by, "css selector")
