"""BigQuery-backed MetadataStore (Phase 4).

Implements the same ``MetadataStore`` interface as the in-memory/JSONL stores, so
a pipeline switches persistence with one line:

    store = BigQueryMetadataStore(project="scb-platform-dev", dataset="scb_metadata_dev")

Writes go to the audit tables created by the `bigquery` Terraform module; reads
back watermarks and file checksums for incremental + idempotent processing.

Testability: all BigQuery access is funnelled through a small ``BQBackend``
protocol. The real backend lazily imports ``google-cloud-bigquery`` (the
``bigquery`` extra); tests inject a fake backend, so no cloud or heavy dependency
is needed to exercise the SQL/row-shaping logic.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from scb_common.metadata import (
    BatchAudit,
    DQResultRecord,
    FileAudit,
    MetadataStore,
)


class BQBackend(Protocol):
    """Minimal surface the store needs from BigQuery."""

    def insert_rows(self, table_id: str, rows: list[dict[str, Any]]) -> list[dict]:
        """Insert rows; return a list of row errors (empty on success)."""

    def run_query(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Run a parameterized query; return result rows as dicts."""


class RealBQBackend:
    """Backend backed by a real ``google.cloud.bigquery.Client`` (lazy import)."""

    def __init__(self, project: str, client: Any = None) -> None:
        if client is None:
            from google.cloud import bigquery  # lazy: only needed for real use

            client = bigquery.Client(project=project)
        self._project = project
        self._client = client

    def insert_rows(self, table_id: str, rows: list[dict[str, Any]]) -> list[dict]:
        return self._client.insert_rows_json(table_id, rows)

    def run_query(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        from google.cloud import bigquery

        type_map = {str: "STRING", int: "INT64", float: "FLOAT64", bool: "BOOL"}
        query_params = [
            bigquery.ScalarQueryParameter(k, type_map.get(type(v), "STRING"), v)
            for k, v in params.items()
        ]
        job = self._client.query(
            sql, job_config=bigquery.QueryJobConfig(query_parameters=query_params)
        )
        return [dict(row) for row in job.result()]


class BigQueryMetadataStore(MetadataStore):
    def __init__(self, project: str, dataset: str, backend: BQBackend | None = None) -> None:
        self.project = project
        self.dataset = dataset
        self._bq = backend or RealBQBackend(project)

    def _tid(self, table: str) -> str:
        return f"{self.project}.{self.dataset}.{table}"

    @staticmethod
    def _check(errors: list[dict], table: str) -> None:
        if errors:
            raise RuntimeError(f"BigQuery insert into {table} failed: {errors}")

    # -- writes ------------------------------------------------------------
    def write_batch(self, audit: BatchAudit) -> None:
        self._check(self._bq.insert_rows(self._tid("batch_audit"), [asdict(audit)]), "batch_audit")

    def write_file(self, audit: FileAudit) -> None:
        self._check(self._bq.insert_rows(self._tid("file_audit"), [asdict(audit)]), "file_audit")

    def write_dq(self, records: list[DQResultRecord]) -> None:
        if not records:
            return
        rows = [asdict(r) for r in records]
        self._check(self._bq.insert_rows(self._tid("dq_results"), rows), "dq_results")

    # -- watermark ---------------------------------------------------------
    def get_watermark(self, entity: str) -> str | None:
        sql = f"SELECT watermark_value FROM `{self._tid('watermark')}` WHERE entity=@entity LIMIT 1"
        rows = self._bq.run_query(sql, {"entity": entity})
        return rows[0]["watermark_value"] if rows else None

    def set_watermark(self, entity: str, value: str) -> None:
        sql = f"""
        MERGE `{self._tid('watermark')}` T
        USING (SELECT @entity AS entity, @value AS watermark_value,
                      CURRENT_TIMESTAMP() AS updated_at) S
        ON T.entity = S.entity
        WHEN MATCHED THEN UPDATE SET watermark_value = S.watermark_value, updated_at = S.updated_at
        WHEN NOT MATCHED THEN INSERT (entity, watermark_value, updated_at)
             VALUES (S.entity, S.watermark_value, S.updated_at)
        """
        self._bq.run_query(sql, {"entity": entity, "value": value})

    # -- dedup -------------------------------------------------------------
    def is_file_seen(self, source: str, checksum: str) -> bool:
        sql = (
            f"SELECT 1 AS hit FROM `{self._tid('file_audit')}` "
            "WHERE source=@source AND checksum=@checksum LIMIT 1"
        )
        return bool(self._bq.run_query(sql, {"source": source, "checksum": checksum}))
