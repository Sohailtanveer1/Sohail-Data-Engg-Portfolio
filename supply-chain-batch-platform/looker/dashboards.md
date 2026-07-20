# Looker Studio Dashboards

Four executive/operational dashboards built on the Gold star schema via the
analytics views in [`bigquery/sql/gold/`](../bigquery/sql/gold). Looker Studio
dashboards are authored in the UI (no code artifact), so this file is the
**definition of record**: data source, KPIs, charts, and filters for each.

Connect Looker Studio → BigQuery → the `${DATASET}` (`scb_gold_<env>`) views.

---

## 1. Inventory Health  ·  source: `vw_inventory_health`

**Question:** Where are we about to stock out, and how much capital is tied up?

| Element | Spec |
|---|---|
| KPI tiles | Total on-hand value · # materials `CRITICAL` · avg days-of-supply |
| Bar | On-hand value by `region` |
| Table | Material × warehouse with `days_of_supply`, `stock_status` (color: CRITICAL=red/LOW=amber/OK=green) |
| Time series | Days-of-supply trend by `category` (use latest per `snapshot_date` — **never SUM** the semi-additive on-hand across days) |
| Filters | `region`, `category`, `snapshot_date` (date range) |

## 2. Supplier Performance  ·  source: `vw_supplier_performance`

**Question:** Which suppliers are reliable, fast, and cost-effective?

| Element | Spec |
|---|---|
| KPI tiles | Avg lead-time days · overall fill rate · total spend |
| Bar | Avg `lead_time_days` by `vendor_name` (sorted) |
| Scatter | `fill_rate` vs `lead_time_days` (bubble = spend) |
| Table | Vendor scorecard: lead time, fill rate, spend, category |
| Filters | `category`, `order_date` |

## 3. Freight Cost  ·  source: `vw_freight_cost`

**Question:** What's our freight cost efficiency and on-time performance by carrier?

| Element | Spec |
|---|---|
| KPI tiles | Total freight cost · avg `cost_per_lb` · on-time % (`AVG(on_time)`) |
| Bar | `cost_per_lb` by `carrier_name` / `mode` |
| Line | Freight cost trend by `ship_date` |
| Table | Carrier × origin_region: cost_per_lb, on-time %, avg transit_days |
| Filters | `mode`, `origin_region`, `ship_date` |

## 4. Order Fulfillment  ·  source: `vw_order_fulfillment`

**Question:** How fast and completely are POs being fulfilled?

| Element | Spec |
|---|---|
| KPI tiles | Avg `cycle_time_days` · overall fill rate · % fully received |
| Histogram | Distribution of `cycle_time_days` |
| Line | Fill rate trend by `order_date` |
| Table | Warehouse × region cycle-time and fill-rate rollup |
| Filters | `region`, `order_date` |

---

## Deploy the views

```bash
# substitute the dataset and create/replace all four views
bash scripts/create_gold_views.sh scb-platform-dev scb_gold_dev
```
Then in Looker Studio: **Create → Data source → BigQuery →** pick each `vw_*`
view, and build the pages above. Share read-only with stakeholders.
