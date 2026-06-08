$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $Root "RUN_APP.ps1")
) -WorkingDirectory $Root

Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:8765"
Write-Host "전자책 출판 로컬 앱을 열었습니다: http://127.0.0.1:8765"
