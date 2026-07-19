# Data Model

The Gold layer is a **Kimball-style dimensional model** (star schemas) built on
top of conformed Silver entities. This document defines the medallion contract
per source, the conformed dimensions, the fact tables, and the SCD strategy.

---

## 1. Modeling principles

- **Conformed dimensions** — `dim_material`, `dim_vendor`, `dim_customer`,
  `dim_warehouse`, `dim_carrier`, `dim_date` are shared across facts so metrics
  are comparable across processes (a warehouse means the same thing to inventory,
  shipments, and receipts).
- **Surrogate keys** — every dimension has an integer/hash **surrogate key** (SK)
  independent of source **business/natural keys** (BK). Facts join on SKs. This
  is what makes SCD2 history possible (multiple SK versions per BK).
- **Grain first** — each fact table's grain is stated explicitly before any
  columns are chosen. Never mix grains in one fact.
- **Additive measures preferred** — fully additive where possible; semi-additive
  (inventory on-hand) flagged so dashboards don't sum across time incorrectly.

---

## 2. Source → medallion mapping

| Source | Silver entities | Feeds (Gold) |
|---|---|---|
| SAP ERP | `material_master`, `vendor`, `purchase_order`, `goods_receipt`, `inventory_valuation` | `dim_material`, `dim_vendor`, `fact_purchase_order`, `fact_goods_receipt`, `fact_inventory_valuation` |
| Salesforce CRM | `customer`, `account`, `sales_rep`, `credit` | `dim_customer`, `dim_sales_rep` |
| WMS (Postgres) | `inventory`, `warehouse_location`, `stock_movement`, `cycle_count` | `dim_warehouse`, `fact_inventory_snapshot`, `fact_stock_movement` |
| TMS (Parquet) | `shipment`, `carrier`, `delivery`, `route`, `freight_cost` | `dim_carrier`, `fact_shipment` |
| Supplier Portal | `supplier_catalog`, `price_list`, `lead_time`, `moq` | `dim_supplier` (⊇ vendor), enriches `fact_purchase_order` |

---

## 3. Conformed dimensions

| Dimension | Grain | Business key (BK) | SCD | History matters because… |
|---|---|---|---|---|
| `dim_material` | one material/SKU | `material_id` | **SCD2** | material attributes (category, UoM, hazmat, std cost) change; historical POs must reflect the attributes *as of* their date |
| `dim_vendor` / `dim_supplier` | one vendor | `vendor_id` | **SCD2** | payment terms, risk rating, address change over time |
| `dim_customer` | one customer | `customer_id` | **SCD2** | credit limit, segment, rep assignment change; needed for point-in-time credit analysis |
| `dim_warehouse` | one warehouse/location | `warehouse_id` | **SCD1** | corrections overwrite; we don't analyze warehouse-attribute history |
| `dim_carrier` | one carrier | `carrier_scac` | **SCD1** | small, slowly changing, no history requirement |
| `dim_sales_rep` | one rep | `rep_id` | **SCD1** | current assignment is what matters |
| `dim_date` | one calendar day | `date_key` (yyyymmdd) | static | generated once; fiscal calendar attributes |

SCD choice rationale is in [ADR-0006](../adr/0006-scd-strategy.md).

**SCD2 columns** (on `dim_material`, `dim_vendor`, `dim_customer`):
`material_sk` (PK/SK) · `material_id` (BK) · business attributes · `effective_from`
· `effective_to` · `is_current` (bool) · `row_hash` (change-detection hash) ·
`batch_id`. Current row has `effective_to = 9999-12-31`, `is_current = true`.

---

## 4. Fact tables

| Fact | Grain | Type | Key measures | Dimensions |
|---|---|---|---|---|
| `fact_purchase_order` | one PO line | transaction | order_qty, unit_price, line_amount, open_qty | material, vendor, warehouse, date (order/expected) |
| `fact_goods_receipt` | one receipt line | transaction | received_qty, receipt_amount | material, vendor, warehouse, date |
| `fact_inventory_snapshot` | one material × warehouse × day | **periodic snapshot** | on_hand_qty, on_hand_value, days_of_supply | material, warehouse, date |
| `fact_stock_movement` | one movement txn | transaction | move_qty (+/-), movement_type | material, warehouse (from/to), date |
| `fact_inventory_valuation` | one material × valuation date | periodic snapshot | valuation_amount, std_cost, moving_avg_cost | material, warehouse, date |
| `fact_shipment` | one shipment (or shipment line) | transaction / accumulating | freight_cost, weight, transit_days, on_time_flag | carrier, warehouse (origin), customer, date (ship/deliver) |

**Grain notes / interview gold:**
- `fact_inventory_snapshot` is **semi-additive**: you can sum on_hand across
  warehouses on the *same day*, but **not** across days. Dashboards must use
  last-value or average over time, not SUM.
- `fact_shipment` with ship + delivery milestones is a candidate **accumulating
  snapshot** (row updated as the shipment progresses) — a good place to discuss
  MERGE/upsert idempotency.
- Late-arriving dimensions: if a PO references a material not yet in
  `dim_material`, we insert an **inferred (early-arriving-fact) member** and
  backfill attributes when they land. ([ADR-0007](../adr/0007-incremental-idempotency.md))

---

## 5. Metadata / control / audit model (BigQuery `*_metadata` dataset)

These tables make the platform metadata-driven, idempotent, and observable.

| Table | Purpose |
|---|---|
| `pipeline_control` | Registry of pipelines/entities: source, entity, load_type (full/incremental), target layer, enabled flag, schedule |
| `source_config` | Connection metadata per source (type, path/endpoint pattern, format, secret ref) |
| `watermark` | Per entity: last successfully processed value (max updated_ts / max id / partition date) for incremental loads |
| `batch_audit` | One row per pipeline run: `batch_id`, pipeline, start/end, status, rows_read/written/rejected, duration, error |
| `file_audit` | One row per ingested file: filename, checksum, size, source, batch_id, status (to prevent reprocessing) |
| `dq_results` | Per batch × rule: rule name, severity, passed/failed counts, sample failing keys |
| `schema_registry` | Registered contract (columns + types) per entity + version for evolution checks |

**batch_id** is the correlation key that ties logs, audit, DQ, and outputs
together across the whole run — the single most important operational field.

---

## 6. Example analytical questions the Gold model answers

1. **Inventory health** — days-of-supply and stockout risk by warehouse/material
   (`fact_inventory_snapshot` × `dim_material` × `dim_warehouse`).
2. **Supplier performance** — on-time delivery, lead-time variance, price trend
   (`fact_purchase_order` + `fact_goods_receipt` + supplier attributes over time).
3. **Freight cost analysis** — cost per lb / per mile by carrier and lane
   (`fact_shipment` × `dim_carrier`).
4. **Order fulfillment** — PO → receipt cycle time and fill rate.
5. **Inventory valuation trend** — capital tied up in stock over time by category.

These map directly to the Looker Studio dashboards planned in Phase 11.
