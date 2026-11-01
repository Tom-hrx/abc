param(
    [string]$BaseUrl = "http://127.0.0.1:5000",
    [string[]]$Image,
    [switch]$Text
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$pyArgs = @((Join-Path $PSScriptRoot "smoke.py"), "--base-url", $BaseUrl)
if ($Text) { $pyArgs += "--text" }
foreach ($item in $Image) { $pyArgs += @("--image", $item) }

& $py @pyArgs
exit $LASTEXITCODE
