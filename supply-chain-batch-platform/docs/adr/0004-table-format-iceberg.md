# ADR-0004 — Silver table format: Apache Iceberg

**Status:** Proposed · **Date:** 2026-07-19

## Context
The Silver layer needs ACID upserts (SCD1/SCD2), idempotent re-runs, schema
evolution, partition evolution, and time travel for auditing/recovery. Plain
Parquet gives none of these transactionally. We also want Silver to be readable
by **BigQuery** (via BigLake) without a copy, to strengthen the lakehouse story.

## Options
1. **Plain Parquet + partition overwrite.** Simplest, no extra libs. But no
   row-level MERGE (hard SCD2), no ACID, manual schema evolution, no time travel.
2. **Delta Lake.** First-class `MERGE`, ACID, evolution, time travel, trivial on
   Spark. But weaker native BigQuery read (Silver wouldn't be BQ-queryable without
   a copy).
3. **Apache Iceberg.** ✅ ACID `MERGE`, schema **and partition** evolution, time
   travel, hidden partitioning, and — decisively — **BigQuery/BigLake can read
   Iceberg tables directly**, so Silver is queryable from BQ with no copy. Broadest
   multi-engine support (Spark, BigQuery, Trino, Flink). Slightly more setup on
   Dataproc (catalog + jars).

## Decision
**Apache Iceberg** for Silver on GCS, using a catalog (Hadoop/GCS catalog for the
portfolio; BigLake Metastore as the enterprise path). Iceberg gives us the same
SCD2/idempotency mechanics as Delta *plus* direct BigQuery readability of Silver
and partition evolution — the strongest lakehouse narrative for interviews.

## Consequences
- ➕ Clean SCD2 / idempotent upserts via Iceberg `MERGE INTO`.
- ➕ Silver is directly queryable from **BigQuery (BigLake external / native
    Iceberg tables)** — no duplicate copy needed for ad-hoc analysis.
- ➕ Schema **and** partition evolution without rewriting data; hidden
    partitioning avoids user partition-column mistakes.
- ➕ Multi-engine + open standard → strong "not locked in" story.
- ➖ More moving parts than Delta: a **catalog** must be configured, and the right
    Iceberg runtime jars/Spark configs supplied to Dataproc Serverless and local
    Spark (a documented setup step in Phase 6).
- ➖ Iceberg tooling/docs are slightly less beginner-smooth than Delta; periodic
    maintenance (`expire_snapshots`, compaction) still required.

## Enterprise vs Portfolio
- **Enterprise:** Iceberg on **BigLake Metastore**, governed by Dataplex; BigQuery
  native Iceberg tables; automated compaction/snapshot expiry.
- **Portfolio:** Iceberg with a GCS-backed catalog + BigLake external tables to
  expose Silver to BigQuery; manual maintenance jobs. The catalog/jar setup is
  captured as a Phase 6 runbook step so it's reproducible.

## Note
Supersedes the initial Delta default. SCD2/idempotency logic
([ADR-0006](0006-scd-strategy.md), [ADR-0007](0007-incremental-idempotency.md))
is unchanged in intent — only the `MERGE` engine differs (Iceberg `MERGE INTO`).
