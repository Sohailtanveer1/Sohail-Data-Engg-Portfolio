# ADR-0001 — Medallion storage layout: GCS lake + BigQuery serving

**Status:** Proposed · **Date:** 2026-07-19

## Context
We need physical homes for Bronze, Silver, and Gold. The platform must showcase
both heavy Spark transformation *and* fast SQL serving, stay cheap on the Free
Trial, and support SCD/MERGE and schema evolution.

## Options
1. **All in BigQuery (ELT).** Load raw → BQ, transform with SQL. Cheap, serverless,
   simplest. But sidelines Spark (a core learning goal) and is awkward for
   file-level lineage, complex Spark-style transforms, and non-tabular sources.
2. **All on GCS (external tables everywhere).** Pure lakehouse. Great for Spark,
   but Looker/serving performance on external tables is worse and governance is
   heavier.
3. **Hybrid: Bronze + Silver on GCS (Spark), Gold in BigQuery (serving).** ✅
   Spark does the heavy lifting where it's strongest; BigQuery serves where it's
   strongest.

## Decision
**Option 3.** Bronze (raw Parquet) and Silver (Iceberg) live on **GCS** and are
processed by **PySpark**. Gold (star schema) and the metadata/audit tables live
in **BigQuery** for serving to Looker Studio.

## Consequences
- ➕ Demonstrates the two headline skills cleanly (Spark lake + BigQuery serving).
- ➕ Cheap: GCS pennies, BigQuery free tier covers Gold; no always-on warehouse.
- ➕ Immutable raw history on cheap object storage enables full replay.
- ➖ Two storage systems to reason about; a GCS→BigQuery load step for Gold.
- ➕ With Iceberg (ADR-0004), Silver *is* directly BigQuery-readable via BigLake —
    no copy needed for ad-hoc analysis.

## Enterprise vs Portfolio
- **Enterprise:** same split, plus BigLake/Iceberg to expose Silver to BigQuery,
  Dataplex for governance, multi-region buckets.
- **Portfolio:** single-region buckets, Gold loaded to BigQuery via Spark BQ
  connector; BigLake deferred.
