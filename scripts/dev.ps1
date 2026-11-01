# 启动开发服务器并打开浏览器。
# 用法：.\scripts\dev.ps1            （默认端口 5000）
#       .\scripts\dev.ps1 -Port 8000
#
# 如果提示"禁止运行脚本"，请改用仓库根目录的 start.cmd（双击即可）。
param(
    [int]$Port = 5000,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "找不到虚拟环境，请先执行：" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt" -ForegroundColor Yellow
    exit 1
}

$serveArgs = @("-m", "flask", "--app", "wsgi", "serve", "--port", "$Port")
if ($NoBrowser) { $serveArgs += "--no-browser" }

Push-Location (Join-Path $root "backend")
try {
    & $python @serveArgs
} finally {
    Pop-Location
}
