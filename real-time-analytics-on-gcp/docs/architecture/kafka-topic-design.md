# Kafka Topic Design

## Naming Convention

`supplychain.<entity>.v<schema-major-version>`

The version is in the topic name, not just the schema file, because a
**breaking** schema change (removing a required field, changing a type) in
Kafka is best handled by cutting a new topic (`v2`) that old and new
consumers can migrate between independently, rather than mutating a topic's
implicit contract underneath running consumers. Additive, backward-compatible
changes (new optional field) stay on `v1` — see the schema evolution rules in
each event's JSON Schema file under `kafka/schemas/`.

## Topics

| Topic | Partition Key | Partitions | Replication | min.insync.replicas | Retention | Why this key |
|---|---|---|---|---|---|---|
| `supplychain.orders.v1` | `order_id` | 6 | 3 | 2 | 7d | All events for one order must land in the same partition to preserve order (CREATED before FULFILLED) |
| `supplychain.inventory.v1` | `warehouse_id:sku` | 6 | 3 | 2 | 7d | Stock movements for one SKU at one warehouse must be ordered relative to each other; unrelated SKUs don't need to be |
| `supplychain.shipments.v1` | `shipment_id` | 3 | 3 | 2 | 7d | Shipment status must progress in order (DISPATCHED before DELIVERED) |
| `supplychain.returns.v1` | `return_id` | 3 | 3 | 2 | 7d | Return lifecycle must be ordered per return |
| `supplychain.suppliers.v1` | `supplier_id` | 3 | 3 | 2 | 14d | Lower event volume, longer retention to support supplier scorecard backfills |
| `<topic>.dlq` (one per domain) | inherited from source | 1 | 3 | 2 | 14d | Low volume by design — growth here is an alert condition, not a scaling problem |

## Why key by ID instead of round-robin

Kafka only guarantees ordering **within a partition**. If we let the producer
round-robin orders across all 6 partitions, a consumer could see
`ORDER_FULFILLED` before `ORDER_CREATED` for the same order, because they
landed on different partitions and were consumed at different rates. Keying
by `order_id` (and `warehouse_id:sku` for inventory) guarantees every event
for that entity is processed in the order it was produced — this is the
cheapest way to get correctness without a stateful reordering step
downstream.

## Why explicit topic creation, not auto-create

`KAFKA_AUTO_CREATE_TOPICS_ENABLE=false` in `kafka/docker/docker-compose.yml`.
Auto-created topics get the broker's default partition count and replication
factor, which is almost never the number you'd actually choose per topic —
and a producer typo in a topic name would silently create a new, empty,
misconfigured topic instead of failing loudly. Explicit creation via
`kafka/docker/create-topics.sh` makes partition count, replication, and
retention a reviewed decision per topic.

## Why replication factor 3 / min.insync.replicas 2 in local dev

This is a deliberate choice to practice production topology even though a
single broker would run fine locally: with `acks=all` on the producer, the
cluster tolerates **one broker going down** without losing an acknowledged
write or pausing writes entirely. It's cheap to demonstrate and is exactly
the configuration you'd defend in an interview about durability guarantees.

## Dead Letter Queues

Every domain topic has a `.dlq` counterpart. A message fails onto the DLQ
when it cannot be parsed or fails schema validation (malformed JSON, missing
required field, wrong type) — this is implemented at the consumer in
Phase 4. The DLQ is intentionally single-partition: ordering doesn't matter
for messages nobody's actively processing, and a human is expected to
inspect it, not a high-throughput consumer.
