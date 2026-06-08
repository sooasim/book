$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Root "scripts\semi_macro_browser.py"
$Books = Join-Path $Root "book_metadata.csv"
$Platforms = Join-Path $Root "platform_registry.csv"
$Profile = Join-Path $Root "publisher_profile_template.csv"
$Mappings = Join-Path $Root "mappings"
$BrowserProfile = Join-Path $Root ".chromium_profile"

python $Script `
  --platform amazon_kdp `
  --book-id zerozone_001 `
  --books $Books `
  --platforms $Platforms `
  --profile $Profile `
  --mapping-dir $Mappings `
  --browser-profile $BrowserProfile `
  --mode assist
