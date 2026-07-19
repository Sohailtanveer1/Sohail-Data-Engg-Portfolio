# Troubleshooting Guide

"Something is actively broken, fix it" procedures. For "an alert fired, is
this expected and what's the likely cause," see
[docs/monitoring-guide.md](monitoring-guide.md) instead — that file covers
backlog, freshness, and latency; this one covers DLQ triage, pipeline
errors, and local dev setup problems.

## dlq-triage

Applies to any of the five domain DLQ topics — an event landed there via
one of three paths: the Kafka consumer (`kafka/consumer/consumer.py`), the
bridge (`bridge/kafka_to_pubsub_bridge.py`), or the Dataflow pipeline
(`dataflow/transforms/parse_and_validate.py`). All three write the same
`{reason, detail, raw_value, ...}` shape, so triage is identical regardless
of which layer caught it.

**Steps:**
1. Pull a few messages without acking, so you don't lose them mid-investigation:
   ```bash
   gcloud pubsub subscriptions pull supplychain.<domain>.v1.dlq-monitoring-sub \
     --limit=5 --auto-ack=false --project=$PROJECT_ID
   ```
   (or, for the Kafka-side DLQ, `kafka-console-consumer.sh --topic supplychain.<domain>.v1.dlq`)
2. Read `reason` — it's always `invalid_json` or `schema_validation_failed`.
3. `schema_validation_failed` with a `detail` naming a field NOT in
   `kafka/schemas/<domain>_event.schema.json` means an upstream producer
   started sending a field the schema doesn't know about yet. See
   [Schema Evolution](architecture/architecture-overview.md#schema-evolution)
   for how to extend a schema without breaking existing consumers — the
   short version: add the field as optional everywhere (JSON Schema, Avro,
   BigQuery Bronze/Silver columns) before any producer starts sending it,
   never after.
4. `invalid_json` almost always means a non-JSON payload landed on a topic
   that shouldn't have one — check `source_system` (present in the DLQ
   record's original event if it parsed partially, or in consumer group
   logs) for which producer sent it.

**Resolution:** fix the schema or the upstream producer. DLQ messages are
NOT automatically reprocessed — if they're valid data that failed only
because the schema lagged behind, replay them by hand after fixing the
schema (see [Replay & Backfill](architecture/architecture-overview.md#replay-and-backfill)).

## dataflow-errors

**Symptom:** the `dataflow_errors` alert fired, or the job graph shows a
step with a rising error count.

**Steps:**
1. Cloud Logging, filtered to:
   ```
   resource.type="dataflow_step"
   resource.labels.job_name="supplychain-streaming-<env>"
   severity>=ERROR
   ```
2. Distinguish expected vs. unexpected errors: `parse_and_validate.py` only
   catches `json.JSONDecodeError`, `UnicodeDecodeError`, and
   `SchemaValidationError` — those route to the DLQ and are NOT bugs.
   Anything else surfacing as an ERROR log here (an `AttributeError`, a
   `KeyError` from a transform assuming a field exists) is an actual bug in
   the pipeline code, not a data quality issue.
3. Worker OOM shows up as the job restarting workers repeatedly with no
   application-level stack trace — check the **Worker Logs** tab's memory
   graph, not just the error log stream.
4. A Flex Template container that fails to start (dependency install
   issue) shows up as the job never reaching `JOB_STATE_RUNNING` — check
   Cloud Build logs from `scripts/deploy_dataflow_pipeline.sh`'s image
   build step first, before looking at the job itself.

## bigquery-write-failures

**Symptom:** the `bigquery_write_failures` alert fired (matches the
literal string `BIGQUERY_WRITE_FAILURE`, which `streaming_pipeline.py`
logs from `write_result.failed_rows_with_errors` — see
`dataflow/pipelines/streaming_pipeline.py`).

**Steps:**
1. Read the full log line — it includes BigQuery's actual error detail
   (schema mismatch, quota exceeded, invalid value), not just "it failed."
2. Schema mismatch is the most common cause: a producer started sending a
   field/type that doesn't match the Bronze table schema
   (`infra/terraform/modules/bigquery/main.tf`). Bronze tables are
   `CREATE_NEVER` — Beam is never allowed to silently evolve them — so the
   fix is a Terraform change to add the column (nullable, so existing rows
   aren't affected), applied and deployed BEFORE the producer starts
   sending the new field, never after.
3. Quota errors (rare at this data volume) mean check the BigQuery quotas
   page for the project — usually a sign something is retrying much faster
   than intended somewhere upstream.

## pipeline-rollback

There's no dedicated rollback workflow by design — see the "Rollback
strategy" comment at the bottom of `.github/workflows/cd-promote.yml`.
Rollback is a forward deploy of a reverted commit:
1. `git revert <bad-commit>` on `main` (or point `cd-promote.yml`'s
   `git_ref` input at the last-known-good tag/SHA).
2. Let CI/CD apply that reverted state normally — same path as any other
   deploy, so there's exactly one deploy mechanism to trust, including for
   undoing a bad one.
3. For the Dataflow job specifically: re-running
   `scripts/deploy_dataflow_pipeline.sh <env>` against the reverted commit
   launches a fresh `--update` against the same job name
   (`supplychain-streaming-<env>`), which Dataflow handles as an in-place
   pipeline graph replacement, not a new job.

## Local development setup problems

**Docker Desktop isn't installed / `docker` not on PATH.** Required for
the local Kafka cluster (`kafka/docker/`). Install from
[docker.com](https://www.docker.com/products/docker-desktop/), then verify
with `docker compose version`.

**`apache-beam` fails to install / `pkg_resources` build errors.** Beam
doesn't support every Python version immediately after it's released — use
Python 3.11 or 3.12 in a dedicated virtualenv for anything touching
`dataflow/`, not whatever the system's newest Python happens to be.
`dataflow/pipelines/requirements.txt` and `dataflow/tests/` were built and
verified against Python 3.12.

**`pip install` fails on `-e ../../common` inside a component's
requirements.txt.** That path is relative to the requirements.txt's own
location — run `pip install -r requirements.txt` from inside the
component's directory (`kafka/producer/`, `bridge/`, etc.), not from the
repo root.

**Terraform `apply` fails on the Pub/Sub Data Transfer Service
impersonation grant.** The `google_service_account_iam_member` binding for
`roles/iam.serviceAccountTokenCreator` (in `infra/terraform/modules/bigquery/main.tf`)
requires the BigQuery Data Transfer API to already be enabled on the
project — confirm `bigquerydatatransfer.googleapis.com` is in the
bootstrap's enabled services list and that bootstrap has actually been
applied before the environment.

**Scheduled query never runs / Silver stays empty.** Check that the
`bq_transform` service account (see `infra/terraform/modules/iam`) has both
the dataset-level grants in the bigquery module AND the
`serviceAccountTokenCreator` grant from the BigQuery Data Transfer service
agent — missing either one makes the scheduled query fail silently rather
than with an obvious error in the Terraform apply itself.
