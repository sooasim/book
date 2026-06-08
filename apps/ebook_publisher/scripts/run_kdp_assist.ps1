$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Root "scripts\semi_macro_browser.py"

python $Script `
  --platform amazon_kdp `
  --book-id zerozone_001 `
  --mode assist
