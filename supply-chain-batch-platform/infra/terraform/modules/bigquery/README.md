# Module: bigquery

Creates BigQuery datasets and tables from JSON schema files under
`schemas/<logical>/<table>.json` (auto-discovered — adding a table is just a new
JSON file). Partition/cluster settings come from `table_options`.

**Inputs:** `project_id`, `location`, `datasets` (logical -> `{dataset_id,
description}`), `table_options` (`"<logical>/<table>"` -> `{partition_field,
clustering}`), `deletion_protection`, `delete_contents_on_destroy`, `labels`.
**Outputs:** `dataset_ids`, `table_ids`.

## Schemas (canonical source of truth)

- `schemas/metadata/` — control/audit/watermark/DQ/schema-registry tables
  (the operational spine, see [data model §5](../../../docs/architecture/data-model.md)).
- `schemas/gold/` — Kimball dims (SCD1/SCD2) and facts.

BigQuery table schema JSON is the standard `[{name,type,mode,description}, …]`
format, so the same files can also be used with `bq mk --schema`.

Free-tier friendly: on-demand pricing, partitioned+clustered facts to cap bytes
scanned, `delete_contents_on_destroy=true` in non-prod for clean teardown.
