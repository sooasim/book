# 사이트 구조 자동 파악(폼 매핑 학습). 로컬에 selenium 설치 필요.
# 사용: .\RUN_SELENIUM_INSPECT.ps1 --platform amazon_kdp
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m pip install -r selenium_bot\requirements-selenium.txt | Out-Null
python -m selenium_bot.cli inspect @args
