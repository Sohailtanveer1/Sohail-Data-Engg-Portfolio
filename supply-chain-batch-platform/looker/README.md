# looker/

Looker Studio dashboard definitions, built on the BigQuery Gold model.
**Implemented in Phase 11.**

- [`dashboards.md`](dashboards.md) — the definition of record for the four
  dashboards (Inventory Health, Supplier Performance, Freight Cost, Order
  Fulfillment): data source, KPIs, charts, filters.
- Powered by the analytics views in [`bigquery/sql/gold/`](../bigquery/sql/gold)
  (`vw_inventory_health`, `vw_supplier_performance`, `vw_freight_cost`,
  `vw_order_fulfillment`).

```bash
bash scripts/create_gold_views.sh <project_id> scb_gold_dev   # create the views
# then connect Looker Studio → BigQuery → each vw_* view
```
