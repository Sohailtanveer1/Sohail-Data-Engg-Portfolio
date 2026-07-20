# bigquery/

BigQuery SQL for the serving and operational layers.

> **Table DDL lives as JSON schemas in the `bigquery` Terraform module**
> ([infra/terraform/modules/bigquery/schemas/](../infra/terraform/modules/bigquery/schemas/))
> — that is the single source of truth (Phase 4), so tables are created and
> destroyed with the stack.

These `sql/` folders hold **transformation** SQL, added later:
- `sql/gold/` — Gold build queries / views (Phase 7)
- `sql/silver/` — optional BigLake external views over Iceberg Silver (Phase 6+)
- `sql/bronze/` — optional external tables (as needed)
- `sql/metadata/` — helper queries (e.g. `dim_date` seed, audit dashboards)
