# Interview Questions

Organized by topic. Each answer references the actual file/decision in
this repo — practice answering without looking, then check against the
reference.

## Architecture

**Q: Why Kafka AND Pub/Sub — why not just Pub/Sub?**
A: Kafka models the realistic on-prem/warehouse-side reality most
enterprises have (a broker they already run), gives durable local
buffering and replay for development without touching billed GCP
resources, and means the platform keeps ingesting during a GCP outage.
Pub/Sub is the cloud-native front door Dataflow reads from natively. See
README's Architecture section.

**Q: Why Medallion architecture instead of one table?**
A: Bronze preserves raw fidelity and full replayability — a bad transform
downstream never destroys the ability to reprocess from source. Silver
conforms and dedupes at event grain (still full history). Gold answers one
business question per view. Separating "append fast" (Bronze, streaming)
from "conform and dedupe" (Silver, batch SQL) lets each be tested and
re-run independently — see `docs/architecture/architecture-overview.md`.

**Q: Walk me through what happens to a single event, start to finish.**
A: Use the sequence diagram in `docs/diagrams/sequence/event-flow-sequence-diagrams.md`
— producer validates and sends keyed to Kafka with `acks=all`; bridge
consumes (separate consumer group), re-validates, publishes to Pub/Sub
with an ordering key, commits its Kafka offset only after the publish
succeeds; Dataflow pulls from an ordered subscription, assigns event-time
timestamps, windows, dedupes by `event_id`, optionally enriches
(shipments), writes to BigQuery Bronze via the Storage Write API; a
scheduled query MERGEs into Silver every 30 minutes; Gold views compute
business answers at query time.

## Idempotency, Deduplication, Exactly-Once

**Q: Is this pipeline exactly-once?**
A: No system is exactly-once end-to-end across heterogeneous components —
the honest, defensible answer is "effectively-once," achieved by layering
at-least-once delivery with idempotent processing at each hop (idempotent
Kafka producer, Beam's windowed state dedup, BigQuery's Storage Write API,
Silver's idempotent MERGE). See the Exactly-Once vs At-Least-Once section
of the architecture doc for the hop-by-hop breakdown.

**Q: Why dedup at three different layers instead of picking the best one?**
A: Each layer catches a different gap the others can't: the producer's
idempotence only covers retried sends within one partition session; Beam's
dedup is scoped to a 60s window + 1hr lateness and catches cross-system
duplicates (e.g. bridge crash-after-publish-before-commit) within that
window; Silver's MERGE catches anything older than that. Defense in depth,
not redundant effort.

**Q: What's the difference between idempotency and deduplication?**
A: Idempotency is a property of an operation — replaying it has the same
effect as running it once (the Silver MERGE is idempotent). Deduplication
is the mechanism that lets an idempotent operation correctly recognize a
repeat as a repeat (the `event_id` key).

## Schema Design & Evolution

**Q: How would you add a new required field to an event without breaking things?**
A: You can't, safely — a required field is a breaking change by
definition. Add it as optional/nullable everywhere first (JSON Schema,
Avro, BigQuery column) deployed ahead of any producer sending it; if it
truly must become required, that's a `v2` topic cut, not a `v1` mutation.
See Schema Evolution in the architecture doc.

**Q: Why `additionalProperties: false` instead of allowing unknown fields through?**
A: Deliberately strict — an unexpected field is treated as a signal worth
investigating (a producer sending something unplanned), not silently
dropped. Trade-off: makes additive schema changes require more discipline
(update the schema first) in exchange for never silently losing data to a
schema drift nobody noticed.

## Kafka Design

**Q: Why key inventory events by `warehouse_id:sku` instead of just `sku`?**
A: Ordering only needs to hold per warehouse-SKU combination. Keying by
`sku` alone would force unrelated warehouses' events onto the same
partition for no ordering benefit, hurting parallelism.

**Q: What does `replication-factor=3` + `min.insync.replicas=2` +
`acks=all` guarantee together?**
A: An acknowledged write survives the loss of any one broker without data
loss or write unavailability. Losing two of three brokers simultaneously
loses write availability (not necessarily data, if the remaining broker
has it) — worth stating precisely rather than "it's durable."

**Q: Why explicit topic creation instead of auto-create?**
A: Auto-created topics get the broker's default partition
count/replication factor almost never the right choice per-topic, and a
producer typo in a topic name silently creates a new empty misconfigured
topic instead of failing loudly.

## Windowing & Watermarking

**Q: Explain watermarking like I've never heard of it.**
A: The watermark is the pipeline's running estimate of "I've likely seen
every event with a timestamp before this point." It's a heuristic based on
event-time progress, not a hard guarantee — which is exactly why
`allowed_lateness` exists as an explicit trade-off between how long you
wait for stragglers versus how fast you get results.

**Q: What happens to an event that arrives after `allowed_lateness` has passed?**
A: It's dropped from the streaming path — Beam's windowed state for that
window has already been garbage collected. It's not lost forever: the GCS
raw archive (written pre-dedup, before the window) captures it, and a
batch replay pipeline can backfill it later. See Replay & Backfill in the
architecture doc.

**Q: Why FixedWindows instead of sessions or sliding windows here?**
A: This pipeline is regular-cadence ingestion (append raw events as they
arrive), not user-behavior analysis — "how many events arrived per
minute" is naturally a fixed-interval question. Session windows fit
gap-based user activity better; sliding windows fit rolling-metric
use cases neither of which describes this pipeline's actual job.

## Partitioning & Clustering

**Q: A query against Bronze is scanning way more data than expected — what do you check first?**
A: Whether the query's `WHERE` clause actually hits the partition column
(`event_timestamp`) with a filter BigQuery's optimizer can use for
partition pruning — a filter wrapped in a function (e.g.
`DATE(event_timestamp) = ...` vs `event_timestamp BETWEEN ...`) can defeat
pruning depending on the exact form. Then check whether the query filters
or groups by the clustering columns — clustering only pays off when the
query pattern matches what it was chosen for.

## IAM & Security

**Q: Walk me through the IAM design for the Dataflow worker.**
A: Least privilege, resource-scoped everywhere it's possible to scope:
`dataflow.worker` + log/metric writer at project level (no narrower scope
exists for those), but Pub/Sub subscriber only on the 5 specific domain
subscriptions, BigQuery dataEditor only on the Bronze dataset (not
project-wide, not Silver/Gold), Secret Manager accessor only on the one
carrier API secret. See `docs/security-guide.md` for the full table.

**Q: Why Workload Identity Federation instead of a downloaded service account key for CI/CD?**
A: No long-lived credential exists to leak — GitHub's own short-lived OIDC
token is exchanged for a GCP token at deploy time, scoped to this exact
repo via an attribute condition. A leaked CI log or compromised dependency
can't be replayed as a standing credential outside an actual workflow run.

## Testing

**Q: How do you unit test windowing/watermark logic without deploying a real streaming job?**
A: Beam's `TestStream` — you control the watermark explicitly (advance it,
add elements at specific timestamps) and assert on what a window
does/doesn't emit. See `dataflow/tests/test_windowing.py`.

## Cost & Operations

**Q: How do you keep BigQuery costs under control on a streaming table that grows every day?**
A: Time partitioning + `require_partition_filter=true` so an unfiltered
query is a hard error, not a surprise bill; auto-expiry on non-prod data;
Gold as views (not materialized) since query-time recompute cost is small
relative to the operational cost of a materialization job at this scale.
See `docs/cost-optimization.md`.

**Q: The pipeline's data freshness alert is firing — what's your triage?**
A: Check whether it correlates with a backlog alert (same root cause,
resolve that first); if backlog is normal but freshness is degraded,
check for events arriving with badly-drifted timestamps (clock skew on a
source system) or a stuck worker holding back the watermark for its key
range. See `docs/monitoring-guide.md#data-freshness`.
