$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$OutPath = Join-Path $Root "toolchain_status.json"

function Test-CommandStatus {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) {
        return [ordered]@{
            name = $Name
            installed = $true
            path = $cmd.Source
        }
    }
    return [ordered]@{
        name = $Name
        installed = $false
        path = $null
    }
}

function Test-PythonModule {
    param([string]$ModuleName)
    $code = "import importlib.util; print('1' if importlib.util.find_spec('$ModuleName') else '0')"
    $result = python -c $code 2>$null
    return [ordered]@{
        name = $ModuleName
        installed = ($result -eq "1")
    }
}

$commands = @(
    "python",
    "pandoc",
    "calibre",
    "ebook-convert",
    "java",
    "node",
    "npm",
    "git",
    "winget"
) | ForEach-Object { Test-CommandStatus $_ }

$pythonModules = @(
    "playwright",
    "ebooklib",
    "bs4",
    "lxml",
    "fitz",
    "reportlab",
    "PIL",
    "weasyprint"
) | ForEach-Object { Test-PythonModule $_ }

$status = [ordered]@{
    checked_at = (Get-Date).ToString("o")
    commands = $commands
    python_modules = $pythonModules
    recommended_winget_packages = @(
        [ordered]@{ name = "Pandoc"; id = "JohnMacFarlane.Pandoc" },
        [ordered]@{ name = "calibre"; id = "calibre.calibre" },
        [ordered]@{ name = "Temurin Java JRE"; id = "EclipseAdoptium.Temurin.21.JRE" },
        [ordered]@{ name = "Sigil"; id = "Sigil-Ebook.Sigil" }
    )
}

$status | ConvertTo-Json -Depth 6 | Set-Content -Path $OutPath -Encoding UTF8

Write-Host "전자책 도구 점검 완료: $OutPath"
Write-Host ""
Write-Host "명령 도구:"
$commands | ForEach-Object {
    $mark = if ($_.installed) { "OK" } else { "MISSING" }
    Write-Host ("- {0}: {1}" -f $_.name, $mark)
}
Write-Host ""
Write-Host "Python 모듈:"
$pythonModules | ForEach-Object {
    $mark = if ($_.installed) { "OK" } else { "MISSING" }
    Write-Host ("- {0}: {1}" -f $_.name, $mark)
}
