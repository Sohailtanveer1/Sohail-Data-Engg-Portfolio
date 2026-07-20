# Phase 7 — Gold: Dimensional Model → BigQuery

> The 15-step walkthrough for the serving layer: build the conformed Kimball star
> from Silver (surrogate-key resolution via point-in-time joins, semi-additive
> handling) and load it into the partitioned BigQuery Gold tables from Phase 4.

> **Execution note:** the fact build is Spark (Silver Iceberg → BigQuery), so it
> needs a JDK/Dataproc like Phase 6. **`dim_date` needs no Spark** and was built
> for real (1,461 rows). Pure builders are unit-tested; the Spark job is
> compile-checked.

---

## 1. Objectives

Assemble Gold facts from Silver by resolving **conformed-dimension surrogate keys**
(point-in-time for SCD2), computing measures, handling late-arriving dimensions,
and loading the star schema to BigQuery for Looker.

## 2. Theory

- **Point-in-time (as-of) join.** A fact joins an SCD2 dim on the business key
  **and** `fact_date ∈ [effective_from, effective_to)` — so a PO reflects the
  material's attributes *as they were on the order date*, not today's.
- **Conformed dimensions.** `dim_material/warehouse/...` are shared across facts,
  so metrics are comparable across processes.
- **Semi-additive measures.** `fact_inventory_snapshot.on_hand_qty` sums across
  warehouses on a day, never across days — a dashboard concern, flagged in the schema.
- **Late-arriving dimensions.** `LEFT JOIN` so a fact referencing a not-yet-loaded
  dim still lands (SK null), backfilled later (ADR-0007).

## 3. Business Context

Gold is what executives actually see. The as-of join is what makes "supplier price
trend" or "credit limit at time of order" correct rather than misleading. Getting
the grain and the join semantics right is the whole game.

## 4. Architecture

```
Silver (Iceberg)                         BigQuery Gold (Phase 4 tables)
  purchase_order ─┐   build_fact_select   ┌─► fact_purchase_order (partitioned by order_date)
  material (SCD2) ─┼─ PIT join → SKs ─────┤
  warehouse(SCD1) ─┘   + measures         └─► (facts...)
  dim_date (generated, no Spark) ───────────► dim_date
```

## 5. Folder Creation

[`spark/transforms/gold.py`](../spark/transforms/gold.py),
[`spark/jobs/gold_job.py`](../spark/jobs/gold_job.py),
[`config/gold/`](../config/gold), [`scripts/build_dim_date.py`](../scripts/build_dim_date.py).

## 6. Infrastructure

Facts load to the partitioned/clustered BigQuery Gold tables from Phase 4 via the
**Spark-BigQuery connector** (indirect write through a temp GCS bucket). `dim_date`
loads directly with the BigQuery client (no Spark).

## 7. Implementation

| Piece | Kind |
|---|---|
| `generate_dim_date` | **pure, runnable** — calendar with fiscal year, weekend flags |
| `pit_join_clause` | **pure** — SCD2 as-of vs SCD1 key-only join |
| `build_fact_select` | **pure** — SK resolution + measures + LEFT JOIN dims |
| `gold_job.py` | Spark — runs the SELECT, writes to BigQuery, audits |
| `config/gold/fact_purchase_order.yaml` | fact→dims mapping + measures |

## 8. Testing / Verification

- **81 tests passing** (+5 Gold: dim_date range/fiscal/weekend, PIT joins, fact SELECT).
- **`dim_date` built for real:** `2024-01-01 → 2027-12-31` = **1,461 rows**, 416
  weekend days, fiscal years 2024–2027, written to `data/gold/dim_date.parquet`
  (and loadable to BigQuery with `--bq-project/--bq-dataset`).
- `gold_job.py` compiles; fact build runs on JDK/Dataproc.

## 9. Documentation

This doc + `config/gold` + PROJECT_PROGRESS.

## 10. Code Review notes

- `LEFT JOIN` for dims is deliberate (late-arriving safe); an `INNER JOIN` would
  silently drop facts whose dimension hasn't loaded yet.
- SCD2 PIT join requires `effective_to` to be exclusive-upper and the current row
  to carry a sentinel far-future `effective_to` (set in Silver, Phase 6).
- `fact_purchase_order` config references `silver.warehouse`, which the Silver
  framework builds the same way as `material` (Phase 6 shipped 2 of the entities;
  the rest are additional config files, not new code).

## 11. Interview Questions

- *What's a point-in-time join and why does it matter?* Joining an SCD2 dim on
  the business key **and** the fact date within the effective window — gives the
  attribute values *as of* the event, essential for correct historical analysis.
- *Conformed dimensions?* Shared dims (same `dim_warehouse` for inventory,
  shipments, receipts) so metrics compare across facts.
- *Why LEFT JOIN dims?* Late-arriving dimensions — the fact still lands; SK backfills.
- *Semi-additive measures?* Inventory on-hand: sum across warehouses, not days.
- *Why generate `dim_date`?* Deterministic calendar with fiscal attributes;
  decouples date logic from every query and enables consistent time analysis.

## 12. Best Practices applied

Conformed dims; as-of joins for SCD2; surrogate-key facts; late-arriving-safe
LEFT JOINs; partitioned/clustered targets; config-driven fact assembly; pure
testable builders.

## 13. Common Mistakes (avoided)

INNER-joining dims (drops facts); "current" join on SCD2 (wrong historical
attributes); SUMming semi-additive snapshots over time; computing measures in the
BI tool instead of the model; forgetting the far-future `effective_to` sentinel.

## 14. Cost Considerations

`dim_date`: **$0** (local generate + tiny BQ load). Fact build on Dataproc
**Serverless**: pay-per-batch (~cents), auto-terminates. BigQuery Gold storage +
Looker queries: free tier (partition+cluster keeps scans small).

## 15. Next Steps

**Phase 8 — Orchestration:** wire the whole daily batch (ingest → Silver → Gold)
into Airflow DAGs (sensors, task groups, retries, SLAs, dynamic-from-metadata),
developed locally then deployed to a **real Cloud Composer** environment (ADR-0003).

---

## Run it

```bash
# dim_date (no Spark) — real now
PYTHONPATH=. python scripts/build_dim_date.py --start 2024-01-01 --end 2027-12-31 \
    [--bq-project scb-platform-dev --bq-dataset scb_gold_dev]

# facts (JDK/Dataproc + BigQuery connector)
gcloud dataproc batches submit pyspark spark/jobs/gold_job.py \
  --region us-central1 --deps-bucket gs://scb-<proj>-dev-dataproc-staging \
  --jars gs://.../iceberg-spark-runtime-3.5_2.12-1.6.1.jar,gs://.../spark-bigquery-with-dependencies.jar \
  -- --entity fact_purchase_order --project scb-platform-dev \
     --dataset scb_gold_dev --temp-bucket scb-<proj>-dev-temp
```
