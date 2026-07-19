# Looker Studio Dashboard Spec

Looker Studio has no meaningful Terraform provider support (dashboards
aren't declared as infrastructure the way a BigQuery view is) — this
document is the specification to build from by hand in the Looker Studio
UI, connected directly to the five Gold views in `supplychain_gold` via
BigQuery's native connector. The step-by-step click-through lives in the
setup guide; this file is *what* to build, not *how to click*.

Every data source below is a Gold view (see `bigquery/sql/gold/`) — never
connect a chart directly to Silver or Bronze. Gold views are cheap,
business-question-shaped, and already handle the "what does 'current
status' mean" logic; connecting to a raw layer just relocates that logic
into the dashboard where it can't be tested or reused.

## Page 1 — Operations Overview

**Data source:** `order_fulfillment_sla`, `inventory_snapshot`

| Tile | Chart type | Fields | Why |
|---|---|---|---|
| Orders within 48h SLA | Scorecard + trend | `AVG(within_48h_sla)` over `created_at` | The single number ops checks first each morning |
| Fulfillment time distribution | Histogram | `fulfillment_hours` | Shows whether misses are a long tail or systemic |
| Low-stock SKUs | Table | `warehouse_id`, `sku`, `current_quantity_on_hand` filtered `low_stock_flag = true` | Directly actionable — this is the reorder list |
| Orders by status | Donut | `current_status`, count | Quick health check |

**Required filter control:** date range on `created_at` — `order_fulfillment_sla`
is a view over Silver, which is unpartitioned-filter-optional, but an
unbounded date range here is still a full-table scan users should not be
able to trigger by accident.

## Page 2 — Shipment Performance

**Data source:** `shipment_performance`

| Tile | Chart type | Fields | Why |
|---|---|---|---|
| On-time delivery rate by carrier | Bar chart | `carrier`, `AVG(NOT delivered_after_estimate)` | The chart that drives "which carrier gets more volume" |
| Transit time by carrier | Box/bar | `carrier`, `transit_hours` | On-time rate alone hides variance — a carrier that's on time but wildly inconsistent is still a problem |
| Delayed shipments | Table | `shipment_id`, `carrier`, `origin_warehouse_id`, `transit_hours` filtered `was_flagged_delayed = true` | Drill-down list for the ops team |

## Page 3 — Returns & Quality

**Data source:** `return_rate_by_reason`

| Tile | Chart type | Fields | Why |
|---|---|---|---|
| Return volume trend | Time series | `return_date`, `SUM(return_count)` | Baseline — is returns volume growing faster than order volume? |
| Return reason breakdown | Stacked bar | `reason_code`, `return_count`, by `warehouse_id` | Isolates whether a quality problem is warehouse-specific |
| Units returned by reason | Table | `reason_code`, `SUM(units_returned)` | What return reasons are actually costing units, not just event count |

## Page 4 — Supplier Scorecard

**Data source:** `supplier_scorecard`

| Tile | Chart type | Fields | Why |
|---|---|---|---|
| Supplier delay rate | Bar chart, sorted descending | `supplier_id`, `delay_rate` | Ranks suppliers by the metric that actually predicts future stockouts |
| PO volume vs. rating | Scatter | `pos_issued` (x), `latest_rating` (y) | Surfaces whether high-volume suppliers are also the well-rated ones |

## Access model

Dashboard viewers need `roles/bigquery.dataViewer` on the `supplychain_gold`
dataset and `roles/bigquery.jobUser` at the project level — both granted via
the `looker_studio_viewers` Terraform variable
(`infra/terraform/environments/<env>/terraform.tfvars`), not by sharing the
dashboard's own link permissions. Looker Studio enforces the underlying
BigQuery IAM on every query it runs; a viewer without those two roles sees
the dashboard shell and a permission error, not the data — which is the
correct failure mode (fix it in Terraform, not by loosening the Looker
Studio share settings).
