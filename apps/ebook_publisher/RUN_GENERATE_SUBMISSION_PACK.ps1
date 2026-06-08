$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Root "scripts\generate_submission_pack.py"
$Books = Join-Path $Root "book_metadata.csv"
$Platforms = Join-Path $Root "platform_registry.csv"
$Out = Join-Path $Root "out"

python $Script --books $Books --platforms $Platforms --out $Out
