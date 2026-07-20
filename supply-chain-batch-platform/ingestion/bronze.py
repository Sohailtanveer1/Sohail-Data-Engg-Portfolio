"""Bronze writer: land raw rows as Parquet with lineage/audit columns.

Bronze contract (architecture §4): exactly what the source sent, plus lineage —
no business logic. Partitioned by ``ingest_date`` under
``<bronze_root>/<source>/<entity>/ingest_date=<date>/<batch_id>.parquet``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from scb_common.context import utcnow

AUDIT_COLS = ["_batch_id", "_source", "_entity", "_source_file",
              "_ingest_ts", "_ingest_date", "_row_hash"]


def row_hash(row: dict[str, Any]) -> str:
    """Deterministic hash of the business content (audit columns excluded)."""
    payload = {k: v for k, v in row.items() if k not in AUDIT_COLS}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def add_audit_columns(rows: list[dict[str, Any]], *, batch_id: str, source: str,
                      entity: str, source_file: str, ingest_date: str) -> list[dict[str, Any]]:
    ts = utcnow().isoformat()
    out = []
    for r in rows:
        out.append({
            **r,
            "_batch_id": batch_id,
            "_source": source,
            "_entity": entity,
            "_source_file": source_file,
            "_ingest_ts": ts,
            "_ingest_date": ingest_date,
            "_row_hash": row_hash(r),
        })
    return out


def write_bronze(rows: list[dict[str, Any]], *, bronze_root: str, source: str,
                 entity: str, batch_id: str, source_file: str, ingest_date: str
                 ) -> tuple[str | None, int]:
    """Write rows to Bronze Parquet; return (path, row_count). Empty -> (None, 0)."""
    if not rows:
        return None, 0
    enriched = add_audit_columns(rows, batch_id=batch_id, source=source, entity=entity,
                                 source_file=source_file, ingest_date=ingest_date)
    out_dir = Path(bronze_root) / source / entity / f"ingest_date={ingest_date}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{batch_id}.parquet"

    df = pd.DataFrame(enriched)
    # Bronze contract: business columns are stored **as strings** (schema-on-read),
    # nulls preserved. This is robust to source messiness — a column that mixes
    # numbers and text (e.g. Excel "unit_price" with ' 310.9 ') would otherwise
    # break Parquet's single-type-per-column rule. Silver (Phase 6) casts to types.
    for col in df.columns:
        if col not in AUDIT_COLS:
            df[col] = df[col].map(lambda v: None if v is None else str(v))
    df.to_parquet(out_path, index=False)
    return str(out_path), len(enriched)
