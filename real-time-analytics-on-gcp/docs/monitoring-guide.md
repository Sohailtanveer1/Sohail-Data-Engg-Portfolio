# Monitoring Guide

Every alert policy in `infra/terraform/modules/monitoring/main.tf` maps to
exactly one operational question. This doc is the on-call runbook for each
one — what it means, what to check first, how to resolve it. The anchors
below (`#pubsub-backlog`, etc.) are linked directly from each alert's
`documentation` block in Cloud Monitoring, so whoever's paged lands here,
not on a generic dashboard.

## Dashboards to build

Cloud Monitoring doesn't get a Terraform-managed dashboard in this repo
(alert *policies* are Terraform-managed; the dashboard layout is a couple
minutes of clicking that isn't worth encoding as IaC at this scale). Build
one dashboard per environment with these charts, sourced from the metrics
each alert below already uses:

- Pub/Sub `num_undelivered_messages` per subscription (backlog + DLQ, same charts the alerts watch)
- Dataflow `data_watermark_age` and `system_lag`
- Dataflow `current_num_vcpus` (worker autoscaling — correlate spikes here with backlog growth)
- BigQuery `query/count` and `storage/uploaded_bytes_billed` on the Bronze dataset (cost tracking, see cost-optimization.md)

## pubsub-backlog

**Alert:** `pubsub_backlog` in the monitoring module, one per domain subscription.

**What it means:** the Dataflow job's read rate from Pub/Sub is falling
behind the publish rate. Not necessarily broken — could be a legitimate
traffic spike the pipeline hasn't scaled up to meet yet.

**First checks, in order:**
1. Cloud Monitoring → Dataflow job → **Autoscaling** tab. Is `current_num_workers`
   climbing? If yes, it's handling it — give it a few minutes before escalating.
2. Check `system_lag` (see `#processing-latency` below) — if lag is also
   climbing, something in the pipeline is slow, not just under-provisioned.
3. Check the job's **Worker Logs** for repeated errors — a worker stuck
   retrying a failed BigQuery write holds up everything behind it in that
   worker's bundle.

**Resolution:** if it's a genuine traffic spike and autoscaling is keeping
up, no action needed — the alert clears itself. If autoscaling is maxed
out (`max_num_workers` reached), that's a capacity conversation, not an
incident: bump `max_num_workers` in the next deploy of
`scripts/deploy_dataflow_pipeline.sh`.

## data-freshness

**Alert:** `data_freshness`, watching `dataflow.googleapis.com/job/data_watermark_age`.

**What it means:** the pipeline's understanding of "now" (the watermark) is
falling behind real time. This is the metric that answers "can I trust
what the dashboard is showing me right now."

**First checks:**
1. Is this correlated with a `pubsub-backlog` alert? If so, it's the same
   root cause (pipeline behind on volume) — resolve that first.
2. If backlog is normal but freshness is degraded, check for late/out-of-
   order events beyond `ALLOWED_LATENESS_SECONDS` (3600s, in
   `dataflow/pipelines/streaming_pipeline.py`) — a warehouse system with a
   badly-drifted clock can single-handedly hold the watermark back if it's
   sending events with far-future or far-past timestamps.
3. Check for a stuck/stalled worker (one worker not making progress holds
   back the watermark for its whole key range) in the Dataflow job's
   **Worker Logs**.

## processing-latency

**Alert:** `processing_latency`, watching `dataflow.googleapis.com/job/system_lag`.

**What it means:** distinct from freshness — a pipeline can be caught up on
watermark but still have high per-element latency if one stage is slow.
In this pipeline, that stage is almost always the shipment enrichment call.

**First checks:**
1. Check `dataflow/transforms/enrich_shipment.py`'s log output for retry
   warnings (`carrier enrichment failed ... after retries`) — a slow or
   flaky third-party carrier API is the single external dependency in this
   pipeline and the most likely source of latency that isn't a capacity issue.
2. If enrichment isn't the cause, check BigQuery Storage Write API latency
   via the `WriteBQ.<domain>` step's per-transform latency in the Dataflow
   job graph UI.

For DLQ triage, Dataflow error investigation, BigQuery write failures, and
pipeline rollback, see [docs/troubleshooting-guide.md](troubleshooting-guide.md)
— those are "something is actively broken, fix it" procedures, kept
separate from this file's "an alert fired, is this expected" runbooks.
