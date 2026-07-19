# Bootstrap the entire local environment (Windows PowerShell).
#   powershell -File scripts/bootstrap_local.ps1 -Date 2026-07-19
#
# 1. generate one day of data for all sources
# 2. start the Docker stack (postgres, mock-salesforce, sftp)
# 3. seed the WMS Postgres from the generated CSVs
# 4. smoke-check the mock Salesforce API

param(
    [string]$Date = (Get-Date -Format "yyyy-MM-dd"),
    [string]$Out  = "data/landing"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

Write-Host "==> 1/4 Generating data for $Date" -ForegroundColor Cyan
python -m data_generators.generate --source all --date $Date --out $Out

Write-Host "==> 2/4 Starting Docker stack" -ForegroundColor Cyan
if (-not (Test-Path "local/.env")) { Copy-Item "local/.env.example" "local/.env" }
docker compose -f local/docker-compose.yml up -d --build
Write-Host "    waiting for Postgres to be healthy..."
Start-Sleep -Seconds 8

Write-Host "==> 3/4 Seeding WMS Postgres" -ForegroundColor Cyan
python scripts/seed_wms.py --date $Date --data-root $Out

Write-Host "==> 4/4 Checking mock Salesforce API" -ForegroundColor Cyan
try { Invoke-RestMethod "http://localhost:8080/health" | ConvertTo-Json -Compress }
catch { Write-Warning "Salesforce mock not ready yet: $_" }

Write-Host "Local environment is up. 'docker compose -f local/docker-compose.yml down' to stop." -ForegroundColor Green
