"""Load generated WMS CSVs into the local Postgres (the WMS source).

    python scripts/seed_wms.py --date 2026-07-19 --data-root data/landing

Reads data/landing/wms/<date>/<entity>.csv and COPYs each into wms.<entity>,
truncating first so re-runs are idempotent. Connection comes from env vars
(defaults match local/.env.example) so no secrets are hard-coded.
"""

from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

import psycopg2

TABLES = ["warehouse_location", "inventory", "stock_movement", "cycle_count"]


def _conn():
    return psycopg2.connect(
        host=os.environ.get("WMS_DB_HOST", "localhost"),
        port=int(os.environ.get("WMS_DB_PORT", "5432")),
        user=os.environ.get("WMS_DB_USER", "wms"),
        password=os.environ.get("WMS_DB_PASSWORD", "wms_local_pw"),
        dbname=os.environ.get("WMS_DB_NAME", "wms"),
    )


def seed(data_root: Path, gen_date: date) -> None:
    base = data_root / "wms" / gen_date.isoformat()
    if not base.is_dir():
        raise SystemExit(f"No WMS data at {base}. Run the generator first.")

    with _conn() as conn, conn.cursor() as cur:
        for table in TABLES:
            csv_path = base / f"{table}.csv"
            if not csv_path.is_file():
                print(f"  skip {table}: {csv_path} missing")
                continue
            cur.execute(f"TRUNCATE wms.{table};")
            with csv_path.open("r", encoding="utf-8") as fh:
                cur.copy_expert(
                    f"COPY wms.{table} FROM STDIN WITH (FORMAT csv, HEADER true)", fh
                )
            cur.execute(f"SELECT count(*) FROM wms.{table};")
            print(f"  loaded wms.{table}: {cur.fetchone()[0]} rows")
        conn.commit()
    print("WMS seed complete.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--data-root", default="data/landing")
    args = ap.parse_args(argv)
    seed(Path(args.data_root), date.fromisoformat(args.date))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
