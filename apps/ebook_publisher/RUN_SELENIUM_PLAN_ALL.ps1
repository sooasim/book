# 저장된 기본정보 1건으로 모든 플랫폼 게시 계획 일괄 생성
# 사용: .\RUN_SELENIUM_PLAN_ALL.ps1 --epub OUT\book.epub --cover OUT\cover.png --out out_plans
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m selenium_bot.cli plan-all @args
