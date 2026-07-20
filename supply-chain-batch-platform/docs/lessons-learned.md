# Lessons Learned

Honest reflections — the trade-offs, the bugs, and what a v2 would change. Being
able to talk about these credibly is worth more than a flawless-looking repo.

---

## What worked well

- **Pure-logic-first design.** Keeping DQ/schema/SCD/DAG logic in pure functions
  (rule → SQL string, MERGE builders, task-graph spec) meant the platform stayed
  fully unit-testable **even though Spark and Airflow couldn't run on the build
  machine**. 94 tests give real confidence in the logic.
- **`batch_id` + audit tables from day one.** Threading one correlation key made
  observability, idempotency, and freshness monitoring fall out naturally later.
- **Metadata-driven onboarding.** Adding a source/entity is a config change. This
  paid off immediately across five very different sources.
- **Cost as a design constraint.** Serverless + guarded Composer + destroy-ability
  means the whole build cost pennies and can't silently drain the trial.

## Bugs caught (and what they taught)

- **Logging handler bound `sys.stdout` once** → broke under pytest's `capsys`.
  Lesson: resolve the stream at emit time; global handler state is a trap.
- **Mixed-type Excel column broke Parquet** (`' 310.9 '` + floats). Lesson: Bronze
  should be schema-on-read strings; don't type at ingest.
- **Three colliding `tests` packages.** Lesson: test dirs shouldn't be importable
  packages unless you need them to be.
- **Freshness dropped failed-only pipelines.** Lesson: "seen but never succeeded"
  is exactly the failure you must alert on.

## Trade-offs made for the Free Trial (and the enterprise version)

| Portfolio choice | Enterprise version |
|---|---|
| Dataproc Serverless + local Spark | autoscaling / ephemeral clusters, reservations |
| Guarded Composer, destroyed between breaks | multiple HA Composer envs |
| Postgres/mock-API/SFTP in Docker | Cloud SQL replica, real Salesforce, managed SFTP |
| Single region | multi-region storage + cross-region standby |
| Iceberg on a GCS/Hadoop catalog | BigLake Metastore + Dataplex governance |
| In-house DQ framework | Great Expectations / Soda + data contracts |
| Manual secrets | CMEK + rotation |

## Known limitations (stated openly)

- Spark/Airflow/Terraform were **not executed on the authoring machine** (no JDK;
  Python 3.14; no live GCP project). Logic is unit-tested, jobs/DAGs compile-checked,
  Terraform validates; runbooks cover real execution.
- Silver/Gold ship **representative** entities; the rest are added via config.
- Salesforce/Excel connectors read the same payloads their live counterparts serve;
  a live-HTTP Salesforce connector is a documented extension.

## What v2 would change

1. Run the full pipeline on real Dataproc Serverless + a short Composer session and
   capture screenshots/lineage.
2. Add BigLake external tables over Iceberg Silver so BigQuery can query Silver
   directly.
3. Expand Silver/Gold to all conformed dims + facts.
4. Add data contracts + a richer profiling step (GE/Soda) and column-level lineage.
5. Add the auto-disable-billing Cloud Function on the budget Pub/Sub topic.
