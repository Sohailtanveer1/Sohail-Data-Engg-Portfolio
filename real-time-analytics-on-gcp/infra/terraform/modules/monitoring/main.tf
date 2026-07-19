# Alert policies map directly to the platform's actual failure modes, not a
# generic "CPU high" checklist — each one answers a specific operational
# question. See docs/monitoring-guide.md for the on-call runbook that goes
# with each alert (what it means, first thing to check, how to resolve).

resource "google_monitoring_notification_channel" "email" {
  project      = var.project_id
  display_name = "Supply Chain Platform On-Call (${var.environment})"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }
}

# 1. Pub/Sub backlog per domain subscription — "is Dataflow keeping up with
#    ingestion?" A growing backlog means the pipeline's processing rate is
#    below the arrival rate; left alone this becomes a freshness problem,
#    then a cost problem (catching up needs more workers), then an outage.
resource "google_monitoring_alert_policy" "pubsub_backlog" {
  for_each     = var.subscription_names
  project      = var.project_id
  display_name = "Pub/Sub backlog growing — ${each.key} (${var.environment})"
  combiner     = "OR"

  conditions {
    display_name = "num_undelivered_messages > threshold for 5m"
    condition_threshold {
      filter          = "resource.type = \"pubsub_subscription\" AND resource.labels.subscription_id = \"${each.value}\" AND metric.type = \"pubsub.googleapis.com/subscription/num_undelivered_messages\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.backlog_threshold
      duration        = "300s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  documentation {
    content   = "Backlog on ${each.key} exceeded ${var.backlog_threshold} messages for 5 minutes. Check the Dataflow job's system_lag and worker autoscaling first — see docs/monitoring-guide.md#pubsub-backlog."
    mime_type = "text/markdown"
  }
}

# 2. DLQ growth — "are we losing/quarantining data right now?" Unlike the
#    backlog alert, ANY sustained message count here is abnormal — a
#    healthy DLQ subscription sits at zero.
resource "google_monitoring_alert_policy" "dlq_growth" {
  for_each     = var.dlq_monitoring_subscription_names
  project      = var.project_id
  display_name = "DLQ receiving messages — ${each.key} (${var.environment})"
  combiner     = "OR"

  conditions {
    display_name = "num_undelivered_messages > 0 for 10m"
    condition_threshold {
      filter          = "resource.type = \"pubsub_subscription\" AND resource.labels.subscription_id = \"${each.value}\" AND metric.type = \"pubsub.googleapis.com/subscription/num_undelivered_messages\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "600s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  documentation {
    content   = "Messages are landing in the ${each.key} DLQ. Pull a few with `gcloud pubsub subscriptions pull ${each.value}` and check the `reason`/`detail` fields — see docs/troubleshooting-guide.md#dlq-triage."
    mime_type = "text/markdown"
  }
}

# 3. Data freshness — Dataflow's own watermark age, i.e. "how far behind
#    event time is the pipeline's understanding of 'now'?" This is the
#    metric that answers "can ops trust the dashboard right now."
resource "google_monitoring_alert_policy" "data_freshness" {
  project      = var.project_id
  display_name = "Pipeline data freshness degraded (${var.environment})"
  combiner     = "OR"

  conditions {
    display_name = "data_watermark_age > threshold for 5m"
    condition_threshold {
      filter          = "resource.type = \"dataflow_job\" AND resource.labels.job_name = \"${var.dataflow_job_name}\" AND metric.type = \"dataflow.googleapis.com/job/data_watermark_age\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.freshness_threshold_seconds
      duration        = "300s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  documentation {
    content   = "Watermark age exceeded ${var.freshness_threshold_seconds}s. Late/out-of-order events beyond the allowed lateness, or a stuck worker, are the usual causes — see docs/monitoring-guide.md#data-freshness."
    mime_type = "text/markdown"
  }
}

# 4. Processing latency — system_lag, i.e. "how long is data sitting in
#    the pipeline before being emitted?" Distinct from freshness: a
#    pipeline can be caught up on watermark but still have high per-element
#    latency if a stage (e.g. the enrichment API call) is slow.
resource "google_monitoring_alert_policy" "processing_latency" {
  project      = var.project_id
  display_name = "Pipeline processing latency high (${var.environment})"
  combiner     = "OR"

  conditions {
    display_name = "system_lag > threshold for 5m"
    condition_threshold {
      filter          = "resource.type = \"dataflow_job\" AND resource.labels.job_name = \"${var.dataflow_job_name}\" AND metric.type = \"dataflow.googleapis.com/job/system_lag\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.latency_threshold_seconds
      duration        = "300s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  documentation {
    content   = "System lag exceeded ${var.latency_threshold_seconds}s. Check the enrichment transform's external API latency first — it's the pipeline's only network call to a third party — see docs/monitoring-guide.md#processing-latency."
    mime_type = "text/markdown"
  }
}

# 5. Dataflow job failure — log-based metric on Dataflow's own error-level
#    logs, alerted the moment any occur. Job state changes (running ->
#    failed) surface in Cloud Logging automatically; we don't need the
#    pipeline to self-report this.
resource "google_logging_metric" "dataflow_errors" {
  project = var.project_id
  name    = "supplychain_dataflow_errors_${var.environment}"
  filter  = "resource.type=\"dataflow_step\" AND severity>=ERROR AND resource.labels.job_name=\"${var.dataflow_job_name}\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_monitoring_alert_policy" "dataflow_errors" {
  # Gated: an alert policy referencing a log-based metric can't be created
  # until Cloud Monitoring has seen that metric, which only happens after
  # the first matching log line is ingested — i.e. after the Dataflow job
  # has actually run. Set enable_logbased_metric_alerts=true and re-apply
  # once the pipeline is live (RUNBOOK Step 9+). The metric itself
  # (google_logging_metric.dataflow_errors above) is created regardless.
  count = var.enable_logbased_metric_alerts ? 1 : 0

  project      = var.project_id
  display_name = "Dataflow job emitting errors (${var.environment})"
  combiner     = "OR"

  conditions {
    display_name = "error log entries > 0 in 5m"
    condition_threshold {
      filter          = "resource.type = \"dataflow_step\" AND metric.type = \"logging.googleapis.com/user/${google_logging_metric.dataflow_errors.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_COUNT"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  documentation {
    content   = "The Dataflow job logged one or more ERROR-severity entries in the last 5 minutes. Check Cloud Logging filtered to this job first — see docs/troubleshooting-guide.md#dataflow-errors."
    mime_type = "text/markdown"
  }
}

# 6. BigQuery write failures — the pipeline logs a specific, greppable
#    message on every failed BigQuery write attempt (see
#    dataflow/pipelines/streaming_pipeline.py WriteToBigQuery error handling)
#    so this log-based metric doesn't have to guess at BigQuery's own log format.
resource "google_logging_metric" "bigquery_write_failures" {
  project = var.project_id
  name    = "supplychain_bq_write_failures_${var.environment}"
  filter  = "resource.type=\"dataflow_step\" AND jsonPayload.message=~\"BIGQUERY_WRITE_FAILURE\" AND resource.labels.job_name=\"${var.dataflow_job_name}\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_monitoring_alert_policy" "bigquery_write_failures" {
  # Gated for the same reason as dataflow_errors above — see that comment.
  count = var.enable_logbased_metric_alerts ? 1 : 0

  project      = var.project_id
  display_name = "BigQuery write failures (${var.environment})"
  combiner     = "OR"

  conditions {
    display_name = "BIGQUERY_WRITE_FAILURE log entries > 0 in 5m"
    condition_threshold {
      filter          = "resource.type = \"dataflow_step\" AND metric.type = \"logging.googleapis.com/user/${google_logging_metric.bigquery_write_failures.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_COUNT"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  documentation {
    content   = "Rows are failing to write to BigQuery Bronze. Common causes: schema mismatch (a producer started sending a field type we don't expect) or a hit quota — see docs/troubleshooting-guide.md#bigquery-write-failures."
    mime_type = "text/markdown"
  }
}
