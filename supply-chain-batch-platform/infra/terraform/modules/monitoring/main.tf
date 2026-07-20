# Observability: log-based metrics extracted from the platform's structured JSON
# logs, plus alert policies (pipeline failure, data freshness, high rejection).
# Cloud Logging/Monitoring free allotment covers this at our volume (~$0).

locals {
  prefix = replace(var.name_prefix, "-", "_") # metric names use underscores
}

# --- Notification channel (email) — created only if an address is provided ----
resource "google_monitoring_notification_channel" "email" {
  count        = var.notification_email == "" ? 0 : 1
  project      = var.project_id
  display_name = "${var.name_prefix} email alerts"
  type         = "email"
  labels = {
    email_address = var.notification_email
  }
}

locals {
  channels = google_monitoring_notification_channel.email[*].id
}

# --- Log-based metrics --------------------------------------------------------
# Our jobs emit one JSON line with message="pipeline_metrics" + status + rows_*.
resource "google_logging_metric" "pipeline_success" {
  project = var.project_id
  name    = "${local.prefix}/pipeline_success"
  filter  = "jsonPayload.message=\"pipeline_metrics\" AND jsonPayload.status=\"success\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "pipeline_failure" {
  project = var.project_id
  name    = "${local.prefix}/pipeline_failure"
  filter  = "jsonPayload.message=\"pipeline_metrics\" AND jsonPayload.status=\"failed\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "rows_rejected" {
  project         = var.project_id
  name            = "${local.prefix}/rows_rejected"
  filter          = "jsonPayload.message=\"pipeline_metrics\""
  value_extractor = "EXTRACT(jsonPayload.rows_rejected)"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
  }
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 16
      growth_factor      = 2
      scale              = 1
    }
  }
}

# --- Alert policies -----------------------------------------------------------
resource "google_monitoring_alert_policy" "pipeline_failure" {
  project      = var.project_id
  display_name = "${var.name_prefix} pipeline failure"
  combiner     = "OR"
  conditions {
    display_name = "A pipeline reported status=failed"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${local.prefix}/pipeline_failure\" AND resource.type=\"global\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      trigger { count = 1 }
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
  notification_channels = local.channels
}

resource "google_monitoring_alert_policy" "data_freshness" {
  project      = var.project_id
  display_name = "${var.name_prefix} data freshness (no successful run)"
  combiner     = "OR"
  conditions {
    display_name = "No successful pipeline run within the freshness window"
    condition_absent {
      filter   = "metric.type=\"logging.googleapis.com/user/${local.prefix}/pipeline_success\" AND resource.type=\"global\""
      duration = "${var.freshness_hours * 3600}s"
      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
  notification_channels = local.channels
}

resource "google_monitoring_alert_policy" "high_rejection" {
  project      = var.project_id
  display_name = "${var.name_prefix} high rejected-row count"
  combiner     = "OR"
  conditions {
    display_name = "Rejected rows above threshold"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${local.prefix}/rows_rejected\" AND resource.type=\"global\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.rejected_rows_threshold
      duration        = "0s"
      trigger { count = 1 }
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_MAX"
      }
    }
  }
  notification_channels = local.channels
}
