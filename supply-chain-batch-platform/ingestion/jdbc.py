"""JDBC (PostgreSQL/WMS) reader for the ingestion layer.

Reads a table incrementally by a watermark column, parallelizable in the real
world via a partition column. Lazy-imports psycopg2 so the rest of the ingestion
package has no DB dependency. Exercised against the local Postgres from Phase 2.
"""

from __future__ import annotations

import os
from typing import Any


def conn_params_from_env() -> dict[str, Any]:
    return {
        "host": os.environ.get("WMS_DB_HOST", "localhost"),
        "port": int(os.environ.get("WMS_DB_PORT", "5432")),
        "user": os.environ.get("WMS_DB_USER", "wms"),
        "password": os.environ.get("WMS_DB_PASSWORD", "wms_local_pw"),
        "dbname": os.environ.get("WMS_DB_NAME", "wms"),
    }


def read_table(schema: str, table: str, *, watermark_column: str | None = None,
               watermark: str | None = None, conn_params: dict[str, Any] | None = None,
               connect: Any = None) -> list[dict[str, Any]]:
    """Read wms.<table>, optionally only rows newer than ``watermark``.

    ``connect`` is injectable for testing (a callable returning a DB-API connection).
    """
    if connect is None:
        import psycopg2  # lazy
        connect = psycopg2.connect
    params = conn_params or conn_params_from_env()

    sql = f'SELECT * FROM "{schema}"."{table}"'
    args: list[Any] = []
    if watermark_column and watermark is not None:
        sql += f' WHERE "{watermark_column}" > %s'
        args.append(watermark)

    conn = connect(**params)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()
