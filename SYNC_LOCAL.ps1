# SYNC_LOCAL.ps1 — GitHub(sooasim/book)의 최신 내용을 로컬 E:\추가프로젝트\book 에 자동 반영
# 사용법(둘 중 하나):
#   1) 이미 받은 폴더에서:   powershell -ExecutionPolicy Bypass -File .\SYNC_LOCAL.ps1
#   2) 최초/어디서나:        아래 "부트스트랩 한 줄"을 PowerShell 에 붙여넣기(파일 없이도 동작)

param(
  [string]$Target = "E:\추가프로젝트\book",
  [string]$Repo   = "https://github.com/sooasim/book.git",
  [string]$Branch = "claude/gallant-hopper-kGgs8"
)

$ErrorActionPreference = "Stop"

function Have($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }
if (-not (Have git)) { Write-Error "git 이 필요합니다. https://git-scm.com 에서 설치 후 다시 실행하세요."; exit 1 }

if (Test-Path (Join-Path $Target ".git")) {
  Write-Host "기존 저장소 갱신: $Target" -ForegroundColor Cyan
  git -C $Target fetch origin
  git -C $Target checkout $Branch
  git -C $Target pull origin $Branch
} else {
  Write-Host "새로 클론: $Repo -> $Target" -ForegroundColor Cyan
  $parent = Split-Path $Target -Parent
  if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
  git clone -b $Branch $Repo $Target
}

Write-Host "`n현재 최신 커밋:" -ForegroundColor Green
git -C $Target log --oneline -1
Write-Host "`n동기화 완료: $Target" -ForegroundColor Green
Write-Host "크롬 확장 적용: chrome://extensions → 개발자 모드 → '압축해제된 확장 로드' → $Target\apps\ebook_publisher\chrome_extension" -ForegroundColor Yellow
