# API Documentation

This platform has no request/response API in the traditional sense — its
"API" is the set of data contracts other systems integrate against: the
event schemas producers must emit, and the Gold views analysts/dashboards
query. Both are treated with the same rigor as a REST API contract:
versioned, validated, and breaking changes require a new version.

## Ingestion contract — event schemas

Producers integrate by publishing to a Kafka topic (or, for a
cloud-native producer, directly to the matching Pub/Sub topic) with a
payload matching that domain's JSON Schema. This is the actual contract —
treat it like an OpenAPI spec:

| Domain | Schema | Kafka / Pub/Sub topic | Partition/ordering key |
|---|---|---|---|
| Orders | [`kafka/schemas/order_event.schema.json`](../../kafka/schemas/order_event.schema.json) | `supplychain.orders.v1` | `order_id` |
| Inventory | [`kafka/schemas/inventory_event.schema.json`](../../kafka/schemas/inventory_event.schema.json) | `supplychain.inventory.v1` | `warehouse_id:sku` |
| Shipments | [`kafka/schemas/shipment_event.schema.json`](../../kafka/schemas/shipment_event.schema.json) | `supplychain.shipments.v1` | `shipment_id` |
| Returns | [`kafka/schemas/return_event.schema.json`](../../kafka/schemas/return_event.schema.json) | `supplychain.returns.v1` | `return_id` |
| Suppliers | [`kafka/schemas/supplier_event.schema.json`](../../kafka/schemas/supplier_event.schema.json) | `supplychain.suppliers.v1` | `supplier_id` |

Every event shares this envelope, regardless of domain:

```json
{
  "event_id": "uuid — idempotency key, must be globally unique per event",
  "event_type": "enum, see the domain schema for valid values",
  "event_timestamp": "ISO-8601, event time — when it happened at the source, not when it was sent",
  "schema_version": "1.0",
  "source_system": "free text, e.g. WMS-EAST-01"
}
```

**Contract rules a producer must follow** (enforced at every hop — see
[docs/architecture/architecture-overview.md#schema-validation--evolution](../architecture/architecture-overview.md)):
- `additionalProperties: false` — sending an undocumented field fails
  validation and routes to the DLQ. Get the field added to the schema
  first, then start sending it.
- `event_id` must be unique per logical event. Sending the same `event_id`
  twice is treated as a duplicate and deduplicated, not as two events.
- A breaking change (new required field, type change) means integrating
  against a new topic version (`v2`), not silently changing `v1`'s shape.

## Consumption contract — Gold views

Analysts, dashboards (Looker Studio), and any downstream service query
these BigQuery views in `supplychain_gold` — never Bronze or Silver
directly (see [looker/dashboard-spec.md](../../looker/dashboard-spec.md)
for why). Each view's SQL is the literal, current contract:

| View | SQL | Answers |
|---|---|---|
| `order_fulfillment_sla` | [`bigquery/sql/gold/order_fulfillment_sla.sql`](../../bigquery/sql/gold/order_fulfillment_sla.sql) | Did this order hit the 48h fulfillment SLA? |
| `inventory_snapshot` | [`bigquery/sql/gold/inventory_snapshot.sql`](../../bigquery/sql/gold/inventory_snapshot.sql) | Current on-hand quantity per warehouse+SKU, right now |
| `shipment_performance` | [`bigquery/sql/gold/shipment_performance.sql`](../../bigquery/sql/gold/shipment_performance.sql) | Transit time and on-time rate per shipment/carrier |
| `return_rate_by_reason` | [`bigquery/sql/gold/return_rate_by_reason.sql`](../../bigquery/sql/gold/return_rate_by_reason.sql) | Daily return volume by warehouse and reason |
| `supplier_scorecard` | [`bigquery/sql/gold/supplier_scorecard.sql`](../../bigquery/sql/gold/supplier_scorecard.sql) | PO reliability and rating per supplier |

**Access:** `roles/bigquery.dataViewer` on `supplychain_gold` +
`roles/bigquery.jobUser` at the project level, granted via the
`looker_studio_viewers` Terraform variable — see
[docs/security-guide.md](../security-guide.md).

**Freshness:** Gold views recompute at query time from Silver, which
refreshes every 30 minutes via scheduled MERGE. A Gold view is never more
than ~30 minutes + query time stale from Bronze — see
[docs/monitoring-guide.md](../monitoring-guide.md) for the freshness SLI
that actually watches this.
