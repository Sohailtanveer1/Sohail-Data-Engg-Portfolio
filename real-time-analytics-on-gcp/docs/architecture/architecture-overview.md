# Architecture Overview

This is the deep-dive companion to the root [README](../../README.md)'s
one-paragraph pitch. Every concept below follows the same structure: why it
exists, the business value, how it's actually implemented in this repo,
how to explain it in an interview, and what the alternatives/trade-offs were.

## End-to-end flow

```
Warehouses (event sources)
      │  Python producer, keyed by business ID
      ▼
Kafka (3-broker KRaft cluster, local Docker)
      │  Kafka-to-Pub/Sub bridge (separate consumer group)
      ▼
Google Pub/Sub (ordered subscriptions, dead-letter policy)
      │  Apache Beam streaming pipeline (Dataflow)
      ▼
BigQuery Bronze (raw, append-only, partitioned + clustered)
      │  Scheduled MERGE (BigQuery Data Transfer Service)
      ▼
BigQuery Silver (deduplicated, conformed, same grain as Bronze)
      │  Plain SQL views
      ▼
BigQuery Gold (business marts — one view per business question)
      │
      ▼
Looker Studio
```

## Idempotency & Deduplication

**Why it exists:** at-least-once delivery is the default at almost every
hop in a distributed system (Kafka retries, Pub/Sub redelivery on nack,
Beam's own retry-on-failure). Without deduplication, a single retried send
becomes a duplicate row, and a duplicate `ORDER_FULFILLED` event could
double-count revenue in a Gold mart.

**Business value:** wrong numbers in a fulfillment SLA or revenue report
erode trust in the platform faster than almost any other failure mode —
this is the thing that gets a data platform's credibility questioned by
finance.

**Enterprise implementation (layered, deliberately not "solved once"):**
1. **Producer:** `enable.idempotence=True` + `acks=all` (`kafka/producer/producer.py`)
   — the Kafka broker itself de-duplicates retried sends within a partition
   session. Does NOT dedup two genuinely separate `produce()` calls with the
   same business event.
2. **Dataflow:** `DeduplicateByEventId` (`dataflow/transforms/deduplicate.py`)
   — stateful DoFn keyed by `event_id`, scoped to a 60s window with 1hr
   allowed lateness. Catches the gap between Kafka and Pub/Sub (e.g. the
   bridge crashing after publishing but before committing its Kafka offset).
3. **Silver:** `MERGE ... WHEN NOT MATCHED` on `event_id`
   (`bigquery/sql/silver/*.sql`) — catches anything that slipped past
   Beam's window-scoped state (a duplicate arriving hours apart).

**Interview explanation:** "idempotency" and "deduplication" are related
but distinct — idempotency means *replaying the same operation twice has
the same effect as once* (the Silver MERGE is idempotent: re-running it
over the same time range is always safe). Deduplication is the mechanism
that makes an idempotent operation actually see duplicates as duplicates
(the `event_id` key is what makes the MERGE's `WHEN NOT MATCHED` clause
correctly identify a repeat).

**Alternatives considered:** a single "exactly-once" mechanism (e.g. only
relying on BigQuery Storage Write API's own exactly-once mode) was rejected
because it only covers the last hop — a duplicate introduced between Kafka
and Pub/Sub would still reach BigQuery as two distinct, valid-looking rows.

## Schema Validation & Evolution

**Why it exists:** a streaming pipeline has no human in the loop reviewing
each message before it's processed — schema validation is the automated
gate that used to be a code reviewer looking at a batch file.

**Business value:** catches a breaking upstream change (a warehouse system
upgrade that renames a field) within seconds via the DLQ alert, instead of
discovering it a week later when a Gold mart's numbers don't add up.

**Enterprise implementation:** JSON Schema files in `kafka/schemas/`
(draft 2020-12, `additionalProperties: false`) are the single source of
truth, loaded by `common/supplychain_common/schema_validator.py` and used
identically by the producer (fail-fast before sending), consumer, bridge,
and Dataflow's `parse_and_validate.py`. The same shape is mirrored as Avro
schemas for Pub/Sub's native schema validation
(`infra/terraform/modules/pubsub/avro_schemas/`) and as BigQuery table
schemas (`infra/terraform/modules/bigquery/main.tf`) — three
representations of the same contract, kept in sync by hand today (a schema
registry would automate this at larger scale — see Alternatives).

### schema-evolution

Rules, in order of preference:
1. **Additive, optional field:** add it as `NULLABLE`/optional everywhere
   (JSON Schema without adding it to `required`, Avro with a `["null", ...]`
   union and a default, BigQuery column as `NULLABLE`) — deploy this BEFORE
   any producer starts sending the field. Old producers keep working
   unchanged; new producers' extra field is accepted.
2. **Required field, or a type change:** this is a breaking change. Cut a
   new topic version (`supplychain.orders.v2`) rather than mutating `v1`'s
   contract underneath consumers that haven't migrated — see the naming
   rationale in `docs/architecture/kafka-topic-design.md`.
3. **Removing a field:** deprecate first (stop relying on it in Gold/Silver
   SQL), confirm nothing reads it, then remove — same v1/v2 topic-cut rule
   if the removal is a required-field change.

**Interview explanation:** "backward compatible" means new schema, old
data still validates. "Forward compatible" means old schema, new data
still validates (usually via ignoring unknown fields, which
`additionalProperties: false` deliberately does NOT allow here — a
stricter-but-safer choice: an unexpected field is treated as a signal
worth investigating, not silently dropped).

**Alternatives:** a managed schema registry (Confluent Schema Registry, or
buf for Protobuf) enforces compatibility rules automatically at publish
time and versions schemas centrally instead of three hand-maintained
representations. Worth the investment past a handful of event types; three
domains × three representations is still hand-maintainable, so it wasn't
added here — flag this trade-off explicitly if asked.

## Dead Letter Queues & Poison Messages

**Why it exists:** a message that can never succeed (malformed JSON, fails
schema validation) will be redelivered forever if you simply retry it —
retrying is the right response to a *transient* failure, and actively
harmful for a *permanent* one, because it wedges the partition/subscription
behind it.

**Business value:** the difference between "one bad event from a
misconfigured warehouse system halts the whole platform" and "one bad
event is quarantined and alerted on while everything else keeps flowing."

**Enterprise implementation:** three independent DLQ layers, each catching
what the previous one missed and each cheaper to fail into than the next:
1. Kafka consumer/bridge write malformed messages to `<topic>.dlq` on the
   Kafka side — rejected before ever leaving the local cluster.
2. Pub/Sub's native `dead_letter_policy` (`infra/terraform/modules/pubsub`)
   catches anything that fails delivery to Dataflow after 5 attempts.
3. Dataflow's own `parse_and_validate.py` DLQ side-output is defense in
   depth for anything that reached this far still malformed.

See [docs/troubleshooting-guide.md#dlq-triage](../troubleshooting-guide.md#dlq-triage)
for the actual triage procedure.

**Interview explanation:** "poison message" specifically means a message
that will fail *every single retry attempt identically* — the defining
property that makes retrying pointless and DLQ-routing correct. Contrast
with a message that fails due to a transient dependency issue (e.g. the
carrier API being briefly down during enrichment) — that gets retried with
backoff, not DLQ'd (see `enrich_shipment.py`'s graceful degradation).

## Out-of-Order & Late-Arriving Events, Watermarking, Windowing

**Why it exists:** in a distributed system, network delay and warehouse-side
batching mean events don't arrive in the order they occurred. A pipeline
that assumes arrival order = event order will occasionally process
`ORDER_FULFILLED` before `ORDER_CREATED` reaches it.

**Business value:** correctness of any time-windowed aggregate (revenue
per hour, orders per day) depends entirely on handling this correctly —
get it wrong and metrics silently undercount or double-count near window
boundaries.

**Enterprise implementation:**
- **Ordering within a key** is guaranteed upstream by Kafka partition
  keys and Pub/Sub's `enable_message_ordering` (both keyed identically —
  see `docs/architecture/kafka-topic-design.md`), so events for the SAME
  entity arrive in order. Events across DIFFERENT entities have no
  ordering guarantee, by design (that's what enables parallelism).
- **Watermarking:** `parse_and_validate.py` assigns each record's Beam
  timestamp from `event_timestamp` (event time), not arrival time — this is
  what makes "late" a meaningful concept at all. Without it, "late" would
  just mean "arrived after some other event," which is trivially always true.
- **Windowing:** `FixedWindows(60s)` with `allowed_lateness=1hr`
  (`streaming_pipeline.py`) — an event within the lateness bound is still
  processed correctly against its original window; anything later is
  dropped from this streaming path (see Replay & Backfill for the recovery
  path for that gap).

**Interview explanation:** the watermark is the pipeline's estimate of "I
have likely seen all events with event_timestamp before this point." It's
a heuristic, not a guarantee — that's exactly why `allowed_lateness`
exists as a tunable trade-off between result latency and completeness.

**Alternatives:** session windows (gaps of inactivity define window
boundaries) fit user-behavior analytics better than this platform's
regular-cadence ingestion; fixed windows were the right fit here since
"how many orders arrived in the last minute" is a naturally fixed-interval
question.

## Partitioning & Clustering

**Why it exists:** BigQuery bills by bytes scanned. An unpartitioned,
unclustered table forces every query to scan the entire table regardless
of how narrow the actual filter is.

**Business value:** the direct cost lever with the best ROI in this
platform — see `docs/cost-optimization.md` for the concrete numbers.

**Enterprise implementation:** every Bronze/Silver table is
`time_partitioning` by `event_timestamp` (DAY granularity) with
`require_partition_filter = true` on Bronze specifically (forces every
query to include a date filter — see the comment in
`infra/terraform/modules/bigquery/main.tf` for why this is relaxed on
Silver). Clustering columns are chosen per-domain to match the actual
query pattern (`warehouse_id, order_id` for orders; `carrier, shipment_id`
for shipments) — clustering only pays off on columns queries actually
filter or aggregate by.

**Interview explanation:** partitioning is coarse (BigQuery can skip whole
partitions without reading them); clustering is fine-grained *within* a
partition (BigQuery sorts data on disk by the clustering key and can skip
blocks that don't match). They compose — partition prunes first, then
clustering prunes further within the surviving partitions.

## Metadata / Audit Columns

**Why it exists:** "when did we receive this" and "which pipeline version
processed it" are questions that only have an answer if captured at write
time — they cannot be reconstructed after the fact.

**Business value:** the difference between a 10-minute debugging session
("this row's `_pipeline_version` matches the bad deploy — rollback,
confirmed") and an open-ended one.

**Enterprise implementation:** `_ingested_at`, `_pubsub_message_id`,
`_pubsub_publish_time`, `_pipeline_version` on every Bronze row (see
`local.audit_columns` in the bigquery module and `AddAuditColumns` in
`dataflow/transforms/add_audit_columns.py`). Silver keeps a trimmed subset
— the two that matter for lineage/dedup, not the full audit trail (Bronze
is the system of record for that).

## Exactly-Once vs. At-Least-Once

**Why it exists:** "exactly-once" is expensive and, across a system with
this many hops (Kafka → Pub/Sub → Dataflow → BigQuery), impossible to
guarantee end-to-end without every single hop supporting it natively —
which none of the open-source/managed pieces here fully do in combination.

**Business value:** knowing exactly where you have at-least-once vs.
exactly-once is what lets you reason correctly about whether "did this
double-count" is even a valid question for a given table.

**Enterprise implementation, hop by hop:**
- Kafka producer → broker: exactly-once *per partition session* (idempotent
  producer).
- Bridge → Pub/Sub: at-least-once (retried publishes on failure, no
  dedup at this hop alone).
- Pub/Sub → Dataflow: at-least-once (Pub/Sub's own redelivery-on-nack).
- Dataflow → BigQuery: **exactly-once**, via the Storage Write API
  (`WriteToBigQuery.Method.STORAGE_WRITE_API` in `streaming_pipeline.py`) —
  the one hop where GCP's managed exactly-once semantics genuinely apply.
- The net effect across all hops: **effectively-once**, achieved by
  composing at-least-once delivery with idempotent processing (dedup by
  `event_id`) rather than any single "exactly-once" mechanism. This is the
  standard, defensible answer — true end-to-end exactly-once across
  heterogeneous systems is not a thing any real platform actually has.

**Interview explanation:** if asked "is this exactly-once," the correct
answer is "no system I've built is exactly-once end-to-end — it's
at-least-once delivery plus idempotent processing, which gives you the
same observable outcome (effectively-once) without requiring every
component to support a distributed transaction."

## Checkpointing & Retries

**Why it exists:** any long-running consumer needs to know "how far have I
gotten" so a restart doesn't reprocess everything from the beginning or,
worse, skip data.

**Enterprise implementation:** Kafka consumer offsets are committed
manually, and only AFTER a message is either successfully processed or
routed to the DLQ (`kafka/consumer/consumer.py`, `bridge/kafka_to_pubsub_bridge.py`)
— never left uncommitted on a validation failure (that would just cause
infinite redelivery of a message that can never succeed). Contrast with a
transient Pub/Sub publish failure in the bridge, which deliberately leaves
the offset uncommitted (see the comment in `kafka_to_pubsub_bridge.py`) —
that failure IS worth retrying via redelivery. Dataflow's own checkpointing
is managed by the runner (Beam's watermark + state mechanism), not
hand-rolled.

**Retries & exponential backoff:** `common/supplychain_common/retry.py`
implements full-jitter exponential backoff, used for Pub/Sub publishes and
the carrier enrichment API call — full jitter specifically avoids every
retrying client waking up in lockstep and re-hammering an already-struggling
dependency, which a fixed or non-jittered backoff curve doesn't prevent.

## Replay and Backfill

**Why it exists:** Kafka retention (7-14 days) and Beam's allowed lateness
(1 hour) both have hard limits — a backfill request for data from three
months ago, or a fix to dedup logic that needs to reprocess history, needs
a source that outlives both.

**Enterprise implementation:** every validated event (pre-dedup, so
duplicates included — a backfill might be re-running specifically because
dedup logic itself needs fixing) is archived as JSON Lines to GCS
(`gs://<project>-raw-event-archive-<env>/<domain>/`, written by
`streaming_pipeline.py` alongside the main BigQuery write) with a lifecycle
policy that ages it to Nearline then Coldline storage rather than deleting
it (`infra/terraform/modules/storage/main.tf`). A backfill re-reads from
this archive with a batch Beam pipeline (not built in this repo — the
archive's existence is the prerequisite; the batch replay pipeline is a
natural v2 addition, reusing the same `parse_and_validate`/`deduplicate`
transforms against `ReadFromText` instead of `ReadFromPubSub`) and
re-runs the same Silver MERGE logic, which is idempotent by construction.

**Interview explanation:** "how would you backfill three months of data"
— the answer isn't "replay Kafka" (retention doesn't go back that far);
it's "read from the GCS raw archive with a batch variant of the same
validated transforms, write to Bronze, let the existing idempotent Silver
MERGE handle the rest correctly regardless of how many times it's re-run."
