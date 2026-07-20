# Developer Guide

Working conventions live in [CONTRIBUTING.md](../CONTRIBUTING.md) and
[docs/standards.md](standards.md). This is the orientation map.

## Where things live
| Layer | Path | Read |
|---|---|---|
| Shared library | `common/scb_common/` | [common/README](../common/README.md) |
| Source emulators | `data_generators/` | [phase-02](phase-02-local-environment.md) |
| Ingestion (→Bronze) | `ingestion/` + `config/sources/` | [phase-05](phase-05-ingestion.md) |
| Spark (Silver/Gold) | `spark/` + `config/{silver,gold}/` | [phase-06](phase-06-spark-silver.md), [phase-07](phase-07-gold.md) |
| Orchestration | `airflow/` | [phase-08](phase-08-orchestration.md) |
| Infra | `infra/terraform/` | [phase-03](phase-03-terraform-foundation.md) |
| Serving | `bigquery/sql/gold/`, `looker/` | [phase-11](phase-11-delivery.md) |

## The golden rules
1. **Pure logic, thin framework** — put testable logic in pure functions; keep
   Spark/Airflow/BigQuery I/O at the edges (that's why the suite runs without them).
2. **Config over code** — onboard entities via `config/`, not new modules.
3. **Idempotent everything** — no blind appends; MERGE / partition-overwrite.
4. **One rule set, two engines** — DQ/schema rules are data (`scb_common`), applied
   locally and in Spark.

## The gate
`black --check . && ruff check . && mypy && pytest -q` + `terraform fmt/validate`.
Install `pre-commit` to run it automatically.
