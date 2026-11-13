# Pack local SQLite + models (+ evaluation) into deploy/seed for the Docker image.
# Run after bootstrap on your PC, then: docker compose build
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Seed = Join-Path $Root "deploy\seed"

$Db = Join-Path $Backend "data\stockpilot.db"
$Models = Join-Path $Backend "artifacts\models"
$Eval = Join-Path $Backend "artifacts\evaluation"

if (-not (Test-Path $Db)) {
    throw "Missing $Db — run .\scripts\bootstrap.ps1 (or --fast) first."
}
if (-not (Test-Path $Models)) {
    throw "Missing $Models — bootstrap/train did not write model artifacts."
}

Write-Host "Clearing $Seed ..."
Get-ChildItem $Seed -Force | Where-Object { $_.Name -ne ".gitkeep" } | Remove-Item -Recurse -Force

New-Item -ItemType Directory -Force -Path $Seed | Out-Null
Copy-Item $Db (Join-Path $Seed "stockpilot.db")
Copy-Item $Models (Join-Path $Seed "models") -Recurse
if (Test-Path $Eval) {
    Copy-Item $Eval (Join-Path $Seed "evaluation") -Recurse
}

$size = (Get-ChildItem $Seed -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Host ("Seed ready under deploy\seed ({0:N1} MB). Next: docker compose build" -f ($size / 1MB))
