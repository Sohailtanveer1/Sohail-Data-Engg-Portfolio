# Phase 6 — Spark Bronze → Silver (Iceberg, DQ, SCD)

> The 15-step walkthrough for the transformation core: PySpark on Iceberg turning
> raw Bronze into clean, typed, deduplicated, quality-gated Silver with SCD1/SCD2
> history — plus the Spark tuning topics.

> **Execution note (read first).** This machine has **no JDK** (and PySpark
> doesn't support Python 3.14), so Spark **cannot run locally here**. The design
> keeps all *logic* in pure builder functions that ARE unit-tested without Spark;
> the Spark orchestration is compile-checked and runs on either a **local JDK +
> pyspark (Python ≤3.12)** or **Dataproc Serverless** — commands in the runbook.

---

## 1. Objectives

Bronze → Silver: **type** (schema cast + evolution), **dedup** (business key),
**quality-gate** (DQ quarantine), and apply **SCD1/SCD2** via **Iceberg
`MERGE INTO`** — idempotently — while demonstrating the Spark performance topics.

## 2. Theory

- **One rule set, two engines.** The Phase-2 `Rule` objects are reused: a pure
  `rule_to_condition` translates each to a Spark SQL predicate. Define quality
  once, run it locally (list[dict]) and in Spark (DataFrame) — no drift.
- **Iceberg SCD2** = two idempotent statements: *close* the open row when
  `row_hash` changed, then *insert* new/changed versions. Re-running is a no-op.
- **Pure builders, thin Spark.** SQL/expression construction is pure and tested;
  Spark just executes the strings. This is what makes an un-runnable-locally Spark
  layer still verifiable.

## 3. Business Context

Silver is the "single source of truth" many consumers could query. It must be
trustworthy: a negative order quantity or an invalid currency can't silently reach
an executive dashboard. The DQ gate quarantines them (auditable), and SCD2 lets
analysts ask "what was this material's standard cost *when* that PO was raised?"

## 4. Architecture

```
Bronze parquet ─► cast to Silver types (NULLIF '' , to_date/to_timestamp)
              ─► dedup: row_number() over business key, keep latest
              ─► DQ gate (evaluate_spark): error rules -> quarantine + dq_results
              ─► add row_hash / effective-dating / surrogate key
              ─► Iceberg MERGE:  SCD2 (history dims) | SCD1/upsert (facts, other dims)
              ─► batch_audit + dq_results ; quarantine parquet for replay
```

## 5. Folder Creation

[`spark/transforms/`](../spark/transforms) (expressions, scd, dq_spark, clean,
session), [`spark/jobs/silver_job.py`](../spark/jobs/silver_job.py),
[`spark/tests/`](../spark/tests), and [`config/silver/`](../config/silver).

## 6. Infrastructure

`session.py` builds a SparkSession with an **Iceberg** catalog (Hadoop catalog +
local/GCS warehouse) and tuning defaults. Local: `spark.jars.packages` pulls the
Iceberg runtime. Dataproc Serverless: the jar is attached to the batch; the same
code runs unchanged.

## 7. Implementation

| File | Pure (tested) | Spark (compile-checked) |
|---|---|---|
| `expressions.py` | cast plan, `rule_to_condition`, `row_hash`, surrogate key, dedup window, Iceberg DDL | — |
| `scd.py` | SCD1/SCD2 MERGE SQL builders | `apply_scd1/2` |
| `dq_spark.py` | — | `evaluate_spark` (uses `rule_to_condition`, FK anti-join, Unique window) |
| `clean.py` | — | `apply_casts`, `apply_dedup`, `add_row_hash/surrogate` |
| `silver_job.py` | — | orchestration + audit |

Config (`config/silver/*.yaml`) declares schema, DQ rules, SCD type, keys, tracked
columns — so a new Silver entity is a config file. Shipped: `material_master`
(SCD2 dim) and `purchase_order` (idempotent fact).

## 8. Testing / Verification

- **76 tests passing** (+13 Spark builder tests: cast plans, every rule's SQL,
  SCD1/SCD2 statements, DDL, dedup window).
- **Cross-phase proof (no Spark):** the real `purchase_order` Bronze (1238 rows)
  run through the *same* Silver DQ config → **31 quarantined** (6 null SKU, 10
  negative qty, 15 bad currency), 1207 clean. The identical `Rule` objects feed
  the Spark gate via `rule_to_condition`.
- Spark modules **compile** (`py_compile`); execution pending a JDK/Dataproc.

## 9. Documentation

This doc + `spark/` & `config/` READMEs + PROJECT_PROGRESS.

## 10. Code Review notes

- Bronze `''` → NULL via `NULLIF` before casting, so empty CSV fields become true
  nulls in Silver (and typed casts don't choke).
- SCD2 surrogate key includes `effective_from` so each version is unique.
- `evaluate_spark` gates on **error**-severity rules only; `warn` rules are
  counted in `dq_results` but don't quarantine.
- Facts use `upsert` (MERGE on business key) not blind append → idempotent re-runs.

## 11. Spark tuning topics (the requested deep-dive)

| Topic | Where / how in this platform |
|---|---|
| **Partitioning** | Silver Iceberg tables partitioned by date; Bronze read prunes by `ingest_date` |
| **Broadcast join** | `autoBroadcastJoinThreshold=64MB` so small conformed dims broadcast (no shuffle) |
| **Shuffle optimization** | `spark.sql.shuffle.partitions` tuned; AQE coalesces post-shuffle |
| **AQE** | enabled — dynamic partition coalescing + skew-join splitting |
| **Skew handling** | `adaptive.skewJoin.enabled` (e.g. a mega-warehouse hot key) |
| **Small-file problem** | AQE coalesce on write + Iceberg `rewrite_data_files` maintenance |
| **Caching/persistence** | cache reused dims within a run (documented in job comments) |
| **Window functions** | dedup via `row_number()`; SCD2 effective-dating |
| **Checkpointing** | long lineage broken with checkpoints on Dataproc (config note) |
| **Dynamic allocation** | Dataproc Serverless autoscaes executors per batch |
| **Idempotent writes** | `partitionOverwriteMode=dynamic` + Iceberg MERGE |

## 12. Best Practices applied

Explicit schemas (never `inferSchema`); pure/testable logic; one rule set two
engines; idempotent MERGE; quarantine-not-drop; AQE + broadcast defaults; config
over code.

## 13. Common Mistakes (avoided)

`inferSchema` in prod; blind append (double counts); SCD2 with overlapping current
rows (hash + `is_current` guard); dropping bad rows silently (we quarantine +
audit); collecting big data to the driver; ignoring small files.

## 14. Cost Considerations

Local Spark: **$0** (needs a JDK). Dataproc **Serverless**: pay-per-batch, **no
idle cost**, ~$0.06–0.20 per Silver batch at this data size; auto-terminates
(ADR-0002). No persistent cluster.

## 15. Next Steps

**Phase 7 — Gold:** build the conformed dims + facts from Silver (surrogate-key
joins, semi-additive handling) and load the star schema into the BigQuery tables
from Phase 4.

---

## Run it (needs a JDK; PySpark on Python ≤3.12)

```bash
# Local (one-time): install a JDK (Temurin 17), then a py3.12 venv with pyspark
py -3.12 -m venv .venv-spark && .venv-spark\Scripts\Activate.ps1
pip install "pyspark==3.5.3" -e common pyyaml pandas pyarrow
python -m data_generators.generate --source sap_erp --date 2026-07-19
python -m ingestion.run --source sap_erp --date 2026-07-19
python -m spark.jobs.silver_job --entity material_master     # SCD2 dim
python -m spark.jobs.silver_job --entity purchase_order      # idempotent fact

# Cloud: submit to Dataproc Serverless (Iceberg jar attached to the batch)
gcloud dataproc batches submit pyspark spark/jobs/silver_job.py \
  --region us-central1 --deps-bucket gs://scb-<proj>-dev-dataproc-staging \
  --jars gs://.../iceberg-spark-runtime-3.5_2.12-1.6.1.jar -- --entity material_master
```
