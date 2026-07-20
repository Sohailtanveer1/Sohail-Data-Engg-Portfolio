# common/

Shared Python package (`scb_common`) used by ingestion, Spark, and Airflow.
**Implemented in Phase 2** (36 unit tests):

| Module | Purpose |
|---|---|
| `logging.py` | Structured JSON logging + the canonical metrics envelope |
| `context.py` | `BatchContext` / `batch_id` — the run correlation key |
| `config.py` | YAML loader with `${ENV:default}` interpolation (config over code) |
| `schema.py` | `TableSchema`/`ColumnSpec` contracts + additive schema evolution |
| `dq.py` | Declarative data-quality rules, quarantine, thresholds ([ADR-0010](../docs/adr/0010-data-quality-framework.md)) |
| `retry.py` | Exponential-backoff retry for transient I/O |
| `metadata.py` | Batch/file/DQ audit + watermark store (in-memory & JSONL) |
| `stores/bigquery.py` | BigQuery-backed `MetadataStore` (Phase 4; `bigquery` extra) |
| `monitoring.py` | Data-freshness report over the audit trail (Phase 9) + CLI |
| `logging.enable_cloud_logging` | Ship structured logs to Cloud Logging (Phase 9) |

Install for dev: `pip install -e common`. Test: `pytest common/tests -q`.
