# 반자동 게시: 폼 자동 채움 + 업로드, 약관/최종 게시는 직접. 세션은 플랫폼별로 유지됨.
# 사용: .\RUN_SELENIUM_ASSIST.ps1 --platform amazon_kdp --book-json book.json --epub OUT\book.epub --cover OUT\cover.png
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m pip install -r selenium_bot\requirements-selenium.txt | Out-Null
python -m selenium_bot.cli assist @args
