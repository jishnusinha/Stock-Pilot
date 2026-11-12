$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Write-Host "StockPilot setup (Windows)"

python --version
node --version
npm --version

$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

Push-Location $Backend
if (-not (Test-Path ".venv")) {
  python -m venv .venv
}
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install --no-cache-dir -r requirements.txt
Pop-Location

Push-Location $Frontend
npm install
Pop-Location

Write-Host ""
Write-Host "Next: .\scripts\bootstrap.ps1 then start-api.ps1 and start-ui.ps1 in separate terminals."
