# Cost Optimization

This project targets running inside a GCP free trial ($300 credit) with
room to spare for actual learning/experimentation. Every cost lever below
is a real trade-off made in this repo, with the reasoning — not a generic
"use partitioning" checklist.

## BigQuery: the biggest lever by far

BigQuery bills primarily by bytes scanned per query (on-demand pricing) —
at this project's data volume, storage cost is close to irrelevant next to
query cost.

- **`require_partition_filter = true` on every Bronze table**
  (`infra/terraform/modules/bigquery/main.tf`). An accidental
  `SELECT * FROM supplychain_bronze.orders` with no `WHERE` on
  `event_timestamp` is the single most expensive mistake a new user of
  this repo could make — a 90-day streaming table scanned in full, every
  time someone forgets a date filter. Forcing the filter makes that
  mistake a query error instead of a surprise line item.
- **Silver/Gold do NOT force a partition filter** — deliberate asymmetry.
  Silver is far smaller (deduplicated, not the full raw stream) and is
  queried more interactively by analysts who shouldn't need to think about
  partition filters for exploratory work. The cost-control case that
  justifies the friction on Bronze doesn't hold at Silver's scale.
- **Gold views, not materialized tables.** Materializing (scheduling a
  table rebuild) trades query-time compute for storage + a maintenance
  job. At this data volume, a Gold view's query-time cost is small enough
  that adding a materialization job would be optimizing a cost that
  doesn't meaningfully exist yet — revisit if/when a Gold view is queried
  often enough that repeated recomputation from Silver actually shows up
  as a cost line.
- **90-day auto-expiry on Bronze in dev/uat** (`expiration_ms` in the
  bigquery module, `null` i.e. no expiry in prod). dev/uat data has no
  long-term value — auto-expiring it means storage cost genuinely can't
  accumulate from repeated demo runs, without anyone remembering to clean up.
- **30-minute Silver refresh cadence**, not more frequent. Every scheduled
  query run has fixed overhead (job startup, metadata reads) independent
  of how much new data there is to process — running every 5 minutes
  instead of 30 multiplies that fixed overhead 6x for a freshness
  improvement most dashboard consumers won't notice. 30 minutes was chosen
  as the point where "real-time enough for ops" and "not paying for
  overhead nobody benefits from" both hold.

## Dataflow

- **Autoscaling, not a fixed worker count** — the job scales workers to
  actual Pub/Sub backlog rather than provisioning for peak load
  permanently. Set `max_num_workers` conservatively for a free-trial
  project (2-4) since Dataflow worker-hours are billed continuously while
  a streaming job runs — this is the single most expensive *continuously
  running* resource in the whole platform, unlike BigQuery/Pub/Sub which
  bill per-use.
- **No public IPs on workers** (see the network diagram) has a secondary
  cost benefit beyond security: no per-worker external IP charge.
- **Stop the job when not actively demoing/developing** — a streaming
  Dataflow job left running 24/7 against a free trial will burn credit
  fastest of anything in this stack. `gcloud dataflow jobs drain` or
  `cancel` between working sessions; redeploy via
  `scripts/deploy_dataflow_pipeline.sh` when you pick it back up.

## Pub/Sub

- Message retention is 7 days on domain topics, 14 on DLQ topics
  (`infra/terraform/modules/pubsub/main.tf`) — long enough to debug a
  backlog or DLQ issue without racing a deadline, not so long that
  storage cost accumulates for messages nobody will ever read again.
  (Pub/Sub's storage cost for unacked/retained messages is real at scale,
  though at this project's message volume it's negligible either way —
  the retention window is chosen for operational usefulness, not cost.)

## Cloud NAT / networking

- A single NAT gateway per environment, not per-subnet or per-worker —
  NAT is billed per-gateway-hour plus per-GB processed; consolidating to
  one gateway per environment is the minimum viable footprint for the one
  outbound use case (carrier API calls) that needs it.

## GCS

- Raw archive bucket lifecycle rules age data to Nearline (30d) then
  Coldline (90d) automatically (`infra/terraform/modules/storage/main.tf`)
  — the archive's whole purpose is "cheap, rarely-read replay source," so
  paying Standard-class prices for 90-day-old data would be pure waste.

## What's NOT optimized, on purpose

Three-broker Kafka replication (`replication-factor=3` in
`kafka/docker/docker-compose.yml`) costs more local disk/CPU than a
single-broker dev setup would. This is a deliberate exception to the
"minimize cost" theme — the Kafka cluster runs entirely locally (zero GCP
cost either way), so there's no financial reason to cut the replication
story short, and the durability trade-off it teaches is worth the local
resource cost.
