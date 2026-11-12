$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
Push-Location $Backend
$env:OMP_NUM_THREADS = "2"
$env:OPENBLAS_NUM_THREADS = "2"
$env:MKL_NUM_THREADS = "2"
$env:STOCKPILOT_THREADS = "2"
.\.venv\Scripts\python -m app.cli bootstrap --products 200 --days 365 --seed 42 --threads 2 @args
Pop-Location
