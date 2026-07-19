#!/usr/bin/env bash
# Bootstrap the entire local environment (Git Bash / WSL / macOS / Linux).
#   scripts/bootstrap_local.sh 2026-07-19
set -euo pipefail

DATE="${1:-$(date +%F)}"
OUT="${2:-data/landing}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

echo "==> 1/4 Generating data for $DATE"
python -m data_generators.generate --source all --date "$DATE" --out "$OUT"

echo "==> 2/4 Starting Docker stack"
[ -f local/.env ] || cp local/.env.example local/.env
docker compose -f local/docker-compose.yml up -d --build
echo "    waiting for Postgres..."
sleep 8

echo "==> 3/4 Seeding WMS Postgres"
python scripts/seed_wms.py --date "$DATE" --data-root "$OUT"

echo "==> 4/4 Checking mock Salesforce API"
curl -s http://localhost:8080/health || echo "(mock not ready yet)"

echo "Local environment is up. 'docker compose -f local/docker-compose.yml down' to stop."
