# spark/

PySpark/Iceberg for the medallion transforms. **Implemented in Phase 6** (Silver).

| Path | Contents |
|---|---|
| `transforms/expressions.py` | **pure** builders: cast plan, `rule_to_condition`, row-hash, surrogate key, dedup window, Iceberg DDL (unit-tested) |
| `transforms/scd.py` | **pure** SCD1/SCD2 `MERGE INTO` SQL builders + Spark appliers |
| `transforms/dq_spark.py` | Spark DQ gate reusing the Phase-2 `Rule` objects |
| `transforms/clean.py` | Spark cast/dedup/hash/surrogate appliers |
| `transforms/session.py` | SparkSession with Iceberg catalog + AQE/tuning defaults |
| `jobs/silver_job.py` | config-driven Bronze→Silver orchestration |
| `tests/` | pure-builder unit tests (no SparkSession needed) |

> **Needs a JDK.** Spark can't run on this repo's Python 3.14 / no-JDK box. Run
> via a local JDK + py3.12 venv or **Dataproc Serverless** — see
> [docs/phase-06-spark-silver.md](../docs/phase-06-spark-silver.md). The *logic*
> is unit-tested without Spark; the jobs are compile-checked.
