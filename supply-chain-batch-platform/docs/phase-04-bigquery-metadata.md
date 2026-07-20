# Phase 4 — BigQuery Datasets, Metadata Model & Gold DDL

> The 15-step walkthrough for the serving + operational layers in BigQuery: two
> datasets, 20 tables (7 metadata/control/audit + 13 Kimball dims & facts), all
> Terraform-managed, plus a BigQuery backend for the metadata store. Free-tier only.

---

## 1. Objectives

- Create the **`scb_metadata_<env>`** (operational spine) and **`scb_gold_<env>`**
  (star schema) datasets and tables via a reusable **`bigquery` Terraform module**.
- Model **control/audit/watermark/DQ/schema-registry** tables — the tables that
  make the platform metadata-driven, idempotent, and observable.
- Model the **Kimball dimensional schema** (SCD1/SCD2 dims + partitioned facts).
- Give `scb_common` a **BigQuery `MetadataStore`** so pipelines persist audit and
  read watermarks in BigQuery with a one-line swap.

## 2. Theory

- **Partitioning vs clustering.** Facts are **date-partitioned** (prune whole days)
  and **clustered** by common filter keys (material/warehouse/carrier) — together
  they cap bytes scanned, which *is* the BigQuery cost model.
- **Surrogate vs business keys.** Dims carry an integer/hash **SK** (per version)
  plus the source **BK**; facts join on SKs, which is what makes SCD2 history work.
- **Semi-additive measures.** `fact_inventory_snapshot.on_hand_qty` can be summed
  across warehouses on a day but **not across days** — flagged in the schema.
- **Money = NUMERIC.** Costs/prices use `NUMERIC` (exact decimal), never FLOAT.
- **Metadata-driven schemas.** Tables are JSON files auto-discovered by the module
  — adding a table is dropping a file (ADR-0005).

## 3. Business Context

The Gold star schema is what executives actually query through Looker (inventory
health, supplier performance, freight cost, fulfilment). The metadata dataset is
what the *operations* team queries: "did last night's batch succeed, how many rows
were rejected, which DQ rule failed, where's the watermark?" Both are first-class.

## 4. Architecture

```
BigQuery
├── scb_metadata_<env>        (operational spine)
│   ├── pipeline_control  source_config  watermark
│   ├── batch_audit*      file_audit*    dq_results*     (*date-partitioned)
│   └── schema_registry
└── scb_gold_<env>            (Kimball star)
    ├── dim_material/vendor/customer   (SCD2: SK + effective dating + is_current + row_hash)
    ├── dim_warehouse/carrier/sales_rep (SCD1: overwrite)
    ├── dim_date
    └── fact_purchase_order / goods_receipt / inventory_snapshot /
        stock_movement / inventory_valuation / shipment   (partitioned + clustered)
```

## 5. Folder Creation

- Canonical table schemas: [`infra/terraform/modules/bigquery/schemas/{metadata,gold}/`](../infra/terraform/modules/bigquery/schemas)
  (JSON, also usable with `bq mk --schema`).
- BigQuery store: [`common/scb_common/stores/bigquery.py`](../common/scb_common/stores/bigquery.py).

## 6. Infrastructure

The **`bigquery` module** auto-discovers `schemas/**/*.json`, creates a dataset per
logical folder, and applies `table_options` (partition field + clustering) per
table. `deletion_protection` and `delete_contents_on_destroy` keep non-prod
teardown clean while protecting prod. Wired into all three env roots.

## 7. Implementation

- **20 table schemas** — 7 metadata (match the `scb_common` audit dataclasses
  exactly, so `asdict()` inserts line up), 13 Gold (SCD1/SCD2 dims + facts).
- **`BigQueryMetadataStore`** — same `MetadataStore` interface as in-memory/JSONL;
  writes audit via streaming insert, reads watermarks/file-checksums via
  parameterized queries, upserts watermarks via `MERGE`. All BigQuery access is
  behind a `BQBackend` protocol so it's unit-tested with a fake (no cloud, no
  heavy dependency); the real backend lazily imports `google-cloud-bigquery`
  (the `bigquery` extra).

## 8. Testing / Verification

- `terraform validate` → **Success** on dev/uat/prod (with the bigquery module).
- `terraform fmt -check` → **clean**.
- All 20 schema files → **valid JSON**.
- `pytest -q` → **52 passed** (6 new BigQuery-store tests via the fake backend).

## 9. Documentation

This doc + `bigquery` module README + updated folder READMEs + PROJECT_PROGRESS.

## 10. Code Review notes

- Audit dataclass fields are kept **1:1** with the BigQuery schemas so inserts
  don't silently drop columns; a schema change must change both (a Phase 9 test
  will assert this alignment).
- `sample_keys` is a `REPEATED STRING` — cast non-string keys to string before
  insert (the dataclass already stores stringifiable values).
- Streaming inserts have a short buffer before rows are queryable; batch audit is
  written at end-of-run so this is not a correctness issue here.

## 11. Interview Questions

- *Partitioning vs clustering — when each?* Partition on the high-cardinality date
  you always filter by (prunes partitions); cluster on secondary keys you filter/
  group by (sorts within partitions). Together they minimise bytes billed.
- *Why NUMERIC for money?* Exact decimal; FLOAT introduces rounding errors that
  are unacceptable for cost/valuation.
- *Why keep audit tables in BigQuery, not just logs?* They're queryable state for
  dashboards, idempotency (watermarks/checksums), and SLA reporting.
- *How does the same code write to JSONL locally and BigQuery in the cloud?* One
  `MetadataStore` interface, multiple backends — dependency inversion.
- *Why surrogate keys on dims?* To version SCD2 rows independently of the business
  key so facts can point at the attribute values *as of* their event date.

## 12. Best Practices applied

Partitioned + clustered facts; NUMERIC money; metadata-driven schema files; one
store interface, swappable backends; least dependencies (BQ optional); prod
deletion-protection; env-parameterised datasets.

## 13. Common Mistakes (avoided)

FLOAT money; unpartitioned facts (full-table scans = surprise cost); SUMming a
semi-additive snapshot across days; embedding business keys as PKs (breaks SCD2);
schema drift between audit dataclasses and BigQuery tables.

## 14. Cost Considerations

| Item | Cost |
|---|---|
| Dataset/table creation | $0 |
| Storage (empty/small) | ~$0 (10 GB/mo free) |
| Queries | first 1 TB/mo free; partition+cluster keeps scans tiny |
| **Phase 4 total** | **~$0** (well inside free tier) |

Teardown: `terraform destroy` (non-prod `delete_contents_on_destroy=true`).

## 15. Next Steps

**Phase 5 — Ingestion (land → Bronze):** metadata-driven extractors (SFTP/REST/
JDBC/GCS) landing all five sources, with `file_audit` checksum dedup, `watermark`
incremental, archive strategy, and Bronze Parquet — writing audit to the tables
built here.

---

## Runbook addition (applies with Phase 3)

After `terraform apply -var-file=dev.tfvars`, the datasets/tables exist:
```bash
bq ls --project_id <project_id>
bq ls <project_id>:scb_metadata_dev
bq ls <project_id>:scb_gold_dev
bq show <project_id>:scb_gold_dev.fact_shipment      # see partition/cluster
```
Use the BigQuery store from a pipeline:
```python
from scb_common.stores.bigquery import BigQueryMetadataStore
store = BigQueryMetadataStore(project="scb-platform-dev", dataset="scb_metadata_dev")
```
