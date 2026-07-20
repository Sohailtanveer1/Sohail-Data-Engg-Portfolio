# Troubleshooting Guide

Symptoms → likely cause → fix. Ordered by where you'll hit them.

---

## Local / Python

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: scb_common` on `python -m ...` | package not installed | `pip install -e common` (pytest works via `pyproject` pythonpath) |
| `ModuleNotFoundError: spark` running `scripts/build_dim_date.py` | repo root not on path | run with `PYTHONPATH=.` (or `python -m`) |
| `pyarrow.lib.ArrowInvalid: Could not convert ' 310.9 '` | mixed-type column to Parquet | expected & handled — Bronze stores business columns **as strings** (see phase-05) |
| Ingestion "skip_duplicate" on a file you changed | checksum unchanged / already processed | it's idempotency working; to force, clear `data/_audit` or land a changed file |
| A source file fails | corrupted/unreadable file | quarantined (`file_audit=failed`), batch continues; inspect the logged error |
| `pytest` import collision on `tests` | duplicate `tests` packages | test dirs must **not** have `__init__.py` (removed by design) |

## Spark / Silver / Gold

| Symptom | Cause | Fix |
|---|---|---|
| `JAVA_HOME is not set` / no `java` | JDK missing | install Temurin 17; PySpark needs a JVM |
| `pyspark` won't install | Python 3.13/3.14 | use Python 3.11/3.12 (`pyspark==3.5.x`) |
| Iceberg `MERGE` / catalog errors | Iceberg runtime jar/catalog missing | attach `iceberg-spark-runtime-3.5_*.jar`; check `spark.sql.catalog.*` config in `session.py` |
| BigQuery write fails from Spark | missing connector / temp bucket | attach `spark-bigquery-with-dependencies.jar`; set `temporaryGcsBucket` |
| SCD2 has duplicate current rows | close-step skipped or hash mismatch | ensure both statements run in order; verify `row_hash` covers tracked cols only |
| Fact rows missing dims (null SK) | late-arriving dimension | expected — LEFT JOIN keeps the fact; backfills when the dim loads |

## Terraform / GCP

| Symptom | Cause | Fix |
|---|---|---|
| `terraform validate` fails after edits | provider not initialized | `terraform init -backend=false` first |
| `Error 409: bucket already exists` | globally-unique name clash | change `bucket_prefix` / `state_bucket_prefix` (include project id) |
| `destroy` fails on non-empty bucket | `force_destroy=false` | dev/uat use `true`; prod protects on purpose — empty it deliberately |
| Composer create fails on IP ranges | secondary ranges missing | ensure `composer-pods`/`composer-services` exist (networking module) |
| Budget apply fails | no billing permission / API off | grant `roles/billing.admin`; enable `cloudbilling.googleapis.com` |
| Permission denied on apply | CI deployer role gap | add the specific role to `ci_deployer_roles` (bootstrap) |

## Airflow / Composer

| Symptom | Cause | Fix |
|---|---|---|
| DAG import error in CI | missing repo dep / bad import | check `PYTHONPATH` + Airflow constraints; run the `dags` CI job locally |
| DAG not appearing | parse error / wrong folder | check scheduler logs; DAG must be under the dags folder |
| Sensor never succeeds | `_SUCCESS` marker path wrong | verify the landing path template + marker exists |
| Composer costs climbing | env left running | **`terraform apply -var enable_composer=false`** (destroy between breaks) |

## Cost / observability

| Symptom | Cause | Fix |
|---|---|---|
| Unexpected spend | Composer or a stuck Dataproc batch | run the cleanup verification in [RUNBOOK §C](../RUNBOOK.md#c-cleanup--verify-0-run-rate) |
| Freshness alert firing | no successful run in window | check `batch_audit` / scheduler; run `python -m scb_common.monitoring` |
| No log-based metrics | logs not structured as jsonPayload | confirm JSON stdout; on GCP it's auto-parsed |
