# One topic + one DLQ topic + one ordered pull subscription per domain.
# Naming mirrors the Kafka topics exactly (see common/supplychain_common/config.py)
# because the bridge is a straight passthrough — same name means "no
# translation table to keep in sync" between the two systems.

data "google_project" "current" {
  project_id = var.project_id
}

locals {
  domains = ["orders", "inventory", "shipments", "returns", "suppliers"]
  # The GCP-managed Pub/Sub service agent is what actually forwards
  # messages to a dead-letter topic — it needs its own publish grant on
  # that topic, separate from any human/SA using the subscription.
  pubsub_service_agent = "service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_topic" "domain" {
  for_each = toset(local.domains)
  project  = var.project_id
  name     = "supplychain.${each.value}.v1"

  message_retention_duration = "604800s" # 7 days — matches the Kafka topic retention

  # No Pub/Sub-level schema binding: the platform speaks plain JSON, but a
  # Pub/Sub AVRO schema (even with encoding=JSON) enforces Avro's JSON
  # encoding, which represents a nullable ["null","string"] field as
  # {"string": "value"} rather than plain "value" — incompatible with the
  # plain JSON every producer here emits. Validation instead happens at the
  # application layers via JSON Schema (kafka/schemas/, applied by the
  # producer, consumer, bridge, and the Dataflow parse_and_validate DoFn),
  # which is the correct tool for plain-JSON payloads. The .avsc files under
  # avro_schemas/ are retained as structural documentation only.
}

resource "google_pubsub_topic" "domain_dlq" {
  for_each = toset(local.domains)
  project  = var.project_id
  name     = "supplychain.${each.value}.v1.dlq"

  message_retention_duration = "1209600s" # 14 days — investigation window
}

resource "google_pubsub_subscription" "domain_dataflow" {
  for_each = toset(local.domains)
  project  = var.project_id
  name     = "supplychain.${each.value}.v1.dataflow-sub"
  topic    = google_pubsub_topic.domain[each.value].id

  # Ordering key = the same business key used for the Kafka partition
  # (order_id, warehouse_id:sku, ...) — see bridge/kafka_to_pubsub_bridge.py.
  # Without this, Pub/Sub's redelivery-on-nack can reorder events within a
  # key even though Kafka delivered them in order.
  enable_message_ordering = true

  ack_deadline_seconds = 60

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.domain_dlq[each.value].id
    max_delivery_attempts = 5
  }

  expiration_policy {
    ttl = "" # never expires due to inactivity
  }
}

# A topic has no observable backlog without a subscription attached to it —
# this subscription exists purely so num_undelivered_messages is a real
# metric the monitoring module can alert on (see modules/monitoring). It's
# never actively read by any consumer; a human investigates via Kafka UI /
# `gcloud pubsub subscriptions pull` when the alert fires, then acks
# manually.
resource "google_pubsub_subscription" "domain_dlq_monitoring" {
  for_each = toset(local.domains)
  project  = var.project_id
  name     = "supplychain.${each.value}.v1.dlq-monitoring-sub"
  topic    = google_pubsub_topic.domain_dlq[each.value].id

  message_retention_duration = "1209600s" # 14 days, matches the DLQ topic
  retain_acked_messages       = false
}

# Grants required for Pub/Sub's dead-letter forwarding to function at all —
# easy to forget and the failure mode (messages just vanish instead of
# reaching the DLQ) is not obvious from the error messages.
resource "google_pubsub_topic_iam_member" "service_agent_publish_dlq" {
  for_each = toset(local.domains)
  project  = var.project_id
  topic    = google_pubsub_topic.domain_dlq[each.value].name
  role     = "roles/pubsub.publisher"
  member   = "serviceAccount:${local.pubsub_service_agent}"
}

resource "google_pubsub_subscription_iam_member" "service_agent_subscriber" {
  for_each     = toset(local.domains)
  project      = var.project_id
  subscription = google_pubsub_subscription.domain_dataflow[each.value].name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${local.pubsub_service_agent}"
}

# --- Application access ------------------------------------------------

resource "google_pubsub_topic_iam_member" "bridge_publisher" {
  for_each = toset(local.domains)
  project  = var.project_id
  topic    = google_pubsub_topic.domain[each.value].name
  role     = "roles/pubsub.publisher"
  member   = "serviceAccount:${var.pubsub_bridge_sa_email}"
}

resource "google_pubsub_subscription_iam_member" "dataflow_worker_subscriber" {
  for_each     = toset(local.domains)
  project      = var.project_id
  subscription = google_pubsub_subscription.domain_dataflow[each.value].name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${var.dataflow_worker_sa_email}"
}

# Dataflow's DLQ side output (see dataflow/pipelines/streaming_pipeline.py)
# republishes malformed messages it catches at the pipeline level — a
# defense-in-depth layer behind the bridge's own Kafka-side DLQ.
resource "google_pubsub_topic_iam_member" "dataflow_worker_dlq_publisher" {
  for_each = toset(local.domains)
  project  = var.project_id
  topic    = google_pubsub_topic.domain_dlq[each.value].name
  role     = "roles/pubsub.publisher"
  member   = "serviceAccount:${var.dataflow_worker_sa_email}"
}
