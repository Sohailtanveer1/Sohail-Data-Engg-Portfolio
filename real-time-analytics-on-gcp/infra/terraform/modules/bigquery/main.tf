# Medallion architecture: Bronze tables are provisioned here and written to
# directly by the Dataflow pipeline (append-only, one row per event, raw
# fidelity preserved via `raw_payload`). Silver and Gold are NOT
# provisioned as empty tables waiting for a pipeline to fill them — Silver
# is materialized by scheduled queries (bigquery/sql/silver/*.sql) and Gold
# is plain views on top of Silver (bigquery/sql/gold/*.sql). Splitting the
# medallion layers this way keeps "append raw events fast" (streaming,
# Beam) separate from "conform and dedupe" (batch SQL, testable in
# isolation, re-runnable without touching Kafka/Pub/Sub at all).

resource "google_bigquery_dataset" "bronze" {
  project    = var.project_id
  dataset_id = "supplychain_bronze"
  location   = var.bq_location

  labels = { layer = "bronze", environment = var.environment }
}

resource "google_bigquery_dataset" "silver" {
  project    = var.project_id
  dataset_id = "supplychain_silver"
  location   = var.bq_location

  labels = { layer = "silver", environment = var.environment }
}

resource "google_bigquery_dataset" "gold" {
  project    = var.project_id
  dataset_id = "supplychain_gold"
  location   = var.bq_location

  labels = { layer = "gold", environment = var.environment }
}

# Every Bronze table shares the same audit/metadata columns (prefixed `_`
# to keep them visually distinct from business fields at a glance):
#   _ingested_at          when Dataflow wrote the row (processing time)
#   _pubsub_message_id    Pub/Sub's own message ID — the practical dedup key
#                          downstream (see bigquery/sql/silver/*.sql QUALIFY)
#   _pubsub_publish_time  when the bridge published to Pub/Sub — used to
#                          measure end-to-end pipeline latency
#   _pipeline_version     which Dataflow pipeline build wrote this row —
#                          essential when debugging "which deploy caused this"
locals {
  audit_columns = [
    { name = "raw_payload", type = "JSON", mode = "NULLABLE", description = "Full original event JSON — safety net if flattened columns lag a schema change." },
    { name = "_ingested_at", type = "TIMESTAMP", mode = "REQUIRED", description = "When the Dataflow pipeline wrote this row." },
    { name = "_pubsub_message_id", type = "STRING", mode = "REQUIRED", description = "Pub/Sub message_id — the practical dedup key (event_id is the logical one)." },
    { name = "_pubsub_publish_time", type = "TIMESTAMP", mode = "REQUIRED", description = "When the bridge published this to Pub/Sub — used for latency SLIs." },
    { name = "_pipeline_version", type = "STRING", mode = "REQUIRED", description = "Dataflow pipeline build/version that wrote this row." },
  ]

  # Silver drops raw_payload (Bronze already keeps it — no need to double
  # the storage cost) and _pubsub_publish_time (a Bronze-only latency SLI
  # concern); it keeps the two columns that matter for lineage/dedup.
  silver_audit_columns = [
    { name = "_ingested_at", type = "TIMESTAMP", mode = "REQUIRED", description = "Carried through from Bronze." },
    { name = "_pubsub_message_id", type = "STRING", mode = "REQUIRED", description = "Carried through from Bronze — still the practical dedup key here." },
    { name = "_pipeline_version", type = "STRING", mode = "REQUIRED", description = "Carried through from Bronze." },
  ]

  # table_id => bigquery/sql/gold/<value>.sql
  gold_views = {
    order_fulfillment_sla  = "order_fulfillment_sla"
    inventory_snapshot     = "inventory_snapshot"
    shipment_performance   = "shipment_performance"
    return_rate_by_reason  = "return_rate_by_reason"
    supplier_scorecard     = "supplier_scorecard"
  }

  bronze_tables = {
    orders = {
      cluster_by = ["warehouse_id", "order_id"]
      schema = [
        { name = "event_id", type = "STRING", mode = "REQUIRED" },
        { name = "event_type", type = "STRING", mode = "REQUIRED" },
        { name = "event_timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
        { name = "schema_version", type = "STRING", mode = "REQUIRED" },
        { name = "source_system", type = "STRING", mode = "REQUIRED" },
        { name = "warehouse_id", type = "STRING", mode = "REQUIRED" },
        { name = "order_id", type = "STRING", mode = "REQUIRED" },
        { name = "customer_id", type = "STRING", mode = "REQUIRED" },
        { name = "order_status", type = "STRING", mode = "REQUIRED" },
        { name = "line_items", type = "RECORD", mode = "REPEATED", fields = [
          { name = "sku", type = "STRING", mode = "REQUIRED" },
          { name = "quantity", type = "INTEGER", mode = "REQUIRED" },
          { name = "unit_price", type = "NUMERIC", mode = "REQUIRED" },
        ] },
      ]
    }
    inventory = {
      cluster_by = ["warehouse_id", "sku"]
      schema = [
        { name = "event_id", type = "STRING", mode = "REQUIRED" },
        { name = "event_type", type = "STRING", mode = "REQUIRED" },
        { name = "event_timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
        { name = "schema_version", type = "STRING", mode = "REQUIRED" },
        { name = "source_system", type = "STRING", mode = "REQUIRED" },
        { name = "warehouse_id", type = "STRING", mode = "REQUIRED" },
        { name = "sku", type = "STRING", mode = "REQUIRED" },
        { name = "quantity_delta", type = "INTEGER", mode = "REQUIRED" },
        { name = "quantity_on_hand", type = "INTEGER", mode = "REQUIRED" },
        { name = "reference_order_id", type = "STRING", mode = "NULLABLE" },
      ]
    }
    shipments = {
      cluster_by = ["carrier", "shipment_id"]
      schema = [
        { name = "event_id", type = "STRING", mode = "REQUIRED" },
        { name = "event_type", type = "STRING", mode = "REQUIRED" },
        { name = "event_timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
        { name = "schema_version", type = "STRING", mode = "REQUIRED" },
        { name = "source_system", type = "STRING", mode = "REQUIRED" },
        { name = "shipment_id", type = "STRING", mode = "REQUIRED" },
        { name = "order_id", type = "STRING", mode = "REQUIRED" },
        { name = "carrier", type = "STRING", mode = "REQUIRED" },
        { name = "tracking_number", type = "STRING", mode = "NULLABLE" },
        { name = "origin_warehouse_id", type = "STRING", mode = "REQUIRED" },
        { name = "destination_postal_code", type = "STRING", mode = "NULLABLE" },
        { name = "estimated_delivery", type = "DATE", mode = "NULLABLE" },
        # Populated by dataflow/transforms/enrich_shipment.py, not by the
        # source event — null whenever the carrier API call was skipped
        # (non-trackable event types) or failed after retries (enrichment
        # failure degrades gracefully; it never blocks the write to Bronze).
        { name = "carrier_live_status", type = "STRING", mode = "NULLABLE" },
        { name = "carrier_eta", type = "TIMESTAMP", mode = "NULLABLE" },
      ]
    }
    returns = {
      cluster_by = ["warehouse_id", "reason_code"]
      schema = [
        { name = "event_id", type = "STRING", mode = "REQUIRED" },
        { name = "event_type", type = "STRING", mode = "REQUIRED" },
        { name = "event_timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
        { name = "schema_version", type = "STRING", mode = "REQUIRED" },
        { name = "source_system", type = "STRING", mode = "REQUIRED" },
        { name = "warehouse_id", type = "STRING", mode = "REQUIRED" },
        { name = "return_id", type = "STRING", mode = "REQUIRED" },
        { name = "order_id", type = "STRING", mode = "REQUIRED" },
        { name = "sku", type = "STRING", mode = "REQUIRED" },
        { name = "quantity", type = "INTEGER", mode = "REQUIRED" },
        { name = "reason_code", type = "STRING", mode = "REQUIRED" },
        { name = "inspection_result", type = "STRING", mode = "NULLABLE" },
      ]
    }
    suppliers = {
      cluster_by = ["supplier_id"]
      schema = [
        { name = "event_id", type = "STRING", mode = "REQUIRED" },
        { name = "event_type", type = "STRING", mode = "REQUIRED" },
        { name = "event_timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
        { name = "schema_version", type = "STRING", mode = "REQUIRED" },
        { name = "source_system", type = "STRING", mode = "REQUIRED" },
        { name = "supplier_id", type = "STRING", mode = "REQUIRED" },
        { name = "po_number", type = "STRING", mode = "NULLABLE" },
        { name = "sku_list", type = "STRING", mode = "REPEATED" },
        { name = "expected_delivery_date", type = "DATE", mode = "NULLABLE" },
        { name = "rating", type = "FLOAT", mode = "NULLABLE" },
      ]
    }
  }
}

resource "google_bigquery_table" "bronze" {
  for_each            = local.bronze_tables
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.bronze.dataset_id
  table_id            = each.key
  deletion_protection = var.environment == "prod"

  time_partitioning {
    type          = "DAY"
    field         = "event_timestamp"
    expiration_ms = var.environment == "prod" ? null : 1000 * 60 * 60 * 24 * 90 # dev/uat: 90-day auto-expiry to control cost; prod: retain
  }

  clustering = each.value.cluster_by

  # Forces every query to include a partition filter (a WHERE on
  # event_timestamp). This is a deliberate cost-control default — an
  # unfiltered SELECT * on a 90-day streaming table is exactly the kind of
  # query that shows up as a surprise line item. Looker Studio dashboards
  # must supply a date range control against this field.
  require_partition_filter = true

  schema = jsonencode(concat(each.value.schema, local.audit_columns))
}

# Silver: same business schema as Bronze (same local.bronze_tables[x].schema
# — the columns don't change between layers, only what's done to fill them),
# minus raw_payload, plus the trimmed audit column set. Not time-partitioned
# with require_partition_filter forced on — Silver is queried more
# interactively by analysts and is far smaller than the 90-day Bronze
# window, so the cost-control tradeoff that justifies forcing a filter on
# Bronze doesn't carry the same weight here.
resource "google_bigquery_table" "silver" {
  for_each            = local.bronze_tables
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.silver.dataset_id
  table_id            = each.key
  deletion_protection = var.environment == "prod"

  time_partitioning {
    type  = "DAY"
    field = "event_timestamp"
  }

  clustering = each.value.cluster_by
  schema     = jsonencode(concat(each.value.schema, local.silver_audit_columns))
}

# One scheduled query per domain, running the MERGE in bigquery/sql/silver/.
# 30-minute cadence is a deliberate middle ground: frequent enough that
# "real-time" dashboards built on Gold aren't stale for hours, infrequent
# enough that BigQuery's per-query overhead doesn't dominate the cost —
# see docs/cost-optimization.md for the actual numbers behind that choice.
resource "google_bigquery_data_transfer_config" "silver_merge" {
  for_each               = local.bronze_tables
  project                = var.project_id
  display_name           = "silver-${each.key}-merge-${var.environment}"
  location                = var.bq_location
  data_source_id          = "scheduled_query"
  schedule                = "every 30 minutes"
  destination_dataset_id  = google_bigquery_dataset.silver.dataset_id
  service_account_name    = var.bq_transform_sa_email

  params = {
    query = file("${path.module}/../../../../bigquery/sql/silver/silver_${each.key}.sql")
  }

  depends_on = [google_bigquery_table.silver, google_bigquery_table.bronze]
}

# Gold: plain views over Silver, not materialized tables — each answers one
# specific business question (see the comment atop each .sql file). Views
# cost nothing to keep "fresh" (they recompute from whatever Silver's
# latest MERGE landed) and are cheap enough at this data volume that
# materializing them would be optimizing a cost that doesn't exist yet.
resource "google_bigquery_table" "gold_views" {
  for_each            = local.gold_views
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.gold.dataset_id
  table_id            = each.key
  deletion_protection = false

  view {
    query          = file("${path.module}/../../../../bigquery/sql/gold/${each.value}.sql")
    use_legacy_sql = false
  }

  depends_on = [google_bigquery_table.silver]
}

# --- Access -----------------------------------------------------------

resource "google_bigquery_dataset_iam_member" "dataflow_worker_bronze_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${var.dataflow_worker_sa_email}"
}

# jobUser (running query/load jobs) is project-scoped in BigQuery's IAM
# model — there's no dataset-level equivalent, which is why this one grant
# lives here instead of being folded into the dataset-level member above.
resource "google_project_iam_member" "dataflow_worker_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${var.dataflow_worker_sa_email}"
}

# Looker Studio connects with the viewer's own Google identity (not a
# service account) when using the native BigQuery connector — so read
# access for a dashboard viewer is a per-person grant here, added as
# people need it, rather than a service account key floating around.
resource "google_bigquery_dataset_iam_member" "gold_viewers" {
  for_each   = toset(var.looker_studio_viewers)
  project    = var.project_id
  dataset_id = google_bigquery_dataset.gold.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = each.value
}

resource "google_project_iam_member" "gold_viewer_job_user" {
  for_each = toset(var.looker_studio_viewers)
  project  = var.project_id
  role     = "roles/bigquery.jobUser"
  member   = each.value
}

# bq_transform runs the scheduled Bronze -> Silver MERGE queries: read on
# Bronze, write on Silver, nothing else — it has no reason to touch Gold
# (those are plain views computed at query time) or any other dataset.
resource "google_bigquery_dataset_iam_member" "bq_transform_bronze_viewer" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${var.bq_transform_sa_email}"
}

resource "google_bigquery_dataset_iam_member" "bq_transform_silver_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.silver.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${var.bq_transform_sa_email}"
}

resource "google_project_iam_member" "bq_transform_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${var.bq_transform_sa_email}"
}

# BigQuery Data Transfer Service's own service agent needs permission to
# mint short-lived tokens AS the bq_transform SA to actually run the
# scheduled query under its identity — easy to miss, and the failure mode
# (scheduled query silently never runs) doesn't point back at this cause.
data "google_project" "current" {
  project_id = var.project_id
}

resource "google_service_account_iam_member" "dts_impersonates_bq_transform" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.bq_transform_sa_email}"
  role                = "roles/iam.serviceAccountTokenCreator"
  member              = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-bigquerydatatransfer.iam.gserviceaccount.com"
}
