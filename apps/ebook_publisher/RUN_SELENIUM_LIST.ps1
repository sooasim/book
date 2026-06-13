# 전 세계 전자책 플랫폼 레지스트리 출력
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m selenium_bot.cli list @args
