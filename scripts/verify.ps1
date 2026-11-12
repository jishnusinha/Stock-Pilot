$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$failed = 0

Push-Location $Backend
Write-Host "== pytest =="
.\.venv\Scripts\python -m pytest -q
if ($LASTEXITCODE -ne 0) { $failed = 1 }
Write-Host "== model-status =="
.\.venv\Scripts\python -m app.cli model-status
if ($LASTEXITCODE -ne 0) { $failed = 1 }
Pop-Location

Push-Location $Frontend
Write-Host "== npm run build =="
npm run build
if ($LASTEXITCODE -ne 0) { $failed = 1 }
Pop-Location

Write-Host "== HTTP health (if API up) =="
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 3
  Write-Host $r.Content
} catch {
  Write-Host "API not running (skip). Start with .\scripts\start-api.ps1"
}

if ($failed -ne 0) { exit 1 }
Write-Host "verify OK"
