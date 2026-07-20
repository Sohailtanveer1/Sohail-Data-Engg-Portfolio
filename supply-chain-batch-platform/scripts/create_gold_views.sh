#!/usr/bin/env bash
# Create/replace the Gold analytics views that power the Looker dashboards.
#   bash scripts/create_gold_views.sh <project_id> <dataset>
# e.g. bash scripts/create_gold_views.sh scb-platform-dev scb_gold_dev
set -euo pipefail

PROJECT="${1:?usage: create_gold_views.sh <project_id> <dataset>}"
DATASET="${2:?usage: create_gold_views.sh <project_id> <dataset>}"
FQ="${PROJECT}.${DATASET}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

for f in "$REPO"/bigquery/sql/gold/vw_*.sql; do
  echo "==> applying $(basename "$f")"
  sed "s/\${DATASET}/${FQ}/g" "$f" | bq query --use_legacy_sql=false --project_id="${PROJECT}"
done
echo "Gold views created in ${FQ}."
