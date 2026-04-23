# OpenEvo local bootstrap (Windows)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host "Installing openevo in editable mode..."
pip install -e .
Write-Host "Starting server on http://127.0.0.1:8765 (Ctrl+C to stop)..."
python -m uvicorn openevo.api.server:app --host 127.0.0.1 --port 8765
