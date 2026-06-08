param(
    [switch]$Install
)

$ErrorActionPreference = "Stop"

$Packages = @(
    @{ Name = "Pandoc"; Id = "JohnMacFarlane.Pandoc" },
    @{ Name = "calibre"; Id = "calibre.calibre" },
    @{ Name = "Temurin Java JRE"; Id = "EclipseAdoptium.Temurin.21.JRE" },
    @{ Name = "Sigil"; Id = "Sigil-Ebook.Sigil" }
)

if (-not $Install) {
    Write-Host "설치 미리보기입니다. 실제 설치하려면 -Install 옵션을 붙이세요."
    $Packages | ForEach-Object {
        Write-Host ("- winget install --id {0} --exact" -f $_.Id)
    }
    exit 0
}

foreach ($pkg in $Packages) {
    Write-Host ""
    Write-Host ("설치 시작: {0} ({1})" -f $pkg.Name, $pkg.Id)
    winget install --id $pkg.Id --exact --accept-package-agreements --accept-source-agreements
}

Write-Host ""
Write-Host "설치 명령 완료. 새 PowerShell 창을 열고 check_ebook_toolchain.ps1을 다시 실행하세요."
