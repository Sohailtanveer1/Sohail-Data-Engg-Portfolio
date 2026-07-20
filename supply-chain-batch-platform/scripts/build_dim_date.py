"""Generate the calendar dimension (dim_date) and load it.

dim_date needs no Spark — it's a deterministic calendar. This script writes it to
local Parquet, and (optionally) loads it straight into BigQuery.

    python scripts/build_dim_date.py --start 2024-01-01 --end 2027-12-31
    python scripts/build_dim_date.py --start 2024-01-01 --end 2027-12-31 \
        --bq-project scb-platform-dev --bq-dataset scb_gold_dev
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from spark.transforms.gold import generate_dim_date


def load_bigquery(rows: list[dict], project: str, dataset: str) -> None:
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    table = f"{project}.{dataset}.dim_date"
    job = client.load_table_from_json(
        rows, table,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE"),
    )
    job.result()
    print(f"Loaded {len(rows)} rows into {table}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-01-01")
    ap.add_argument("--end", default="2027-12-31")
    ap.add_argument("--fiscal-start-month", type=int, default=1)
    ap.add_argument("--out", default="data/gold/dim_date.parquet")
    ap.add_argument("--bq-project", default=None)
    ap.add_argument("--bq-dataset", default=None)
    args = ap.parse_args(argv)

    rows = generate_dim_date(date.fromisoformat(args.start), date.fromisoformat(args.end),
                             fiscal_start_month=args.fiscal_start_month)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out, index=False)
    print(f"dim_date: {len(rows)} rows -> {out.resolve()}")

    if args.bq_project and args.bq_dataset:
        load_bigquery(rows, args.bq_project, args.bq_dataset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
