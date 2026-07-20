output "notification_channel_ids" {
  description = "Created notification channel ids (empty if no email)."
  value       = google_monitoring_notification_channel.email[*].id
}

output "alert_policy_names" {
  description = "Names of the alert policies created."
  value = [
    google_monitoring_alert_policy.pipeline_failure.display_name,
    google_monitoring_alert_policy.data_freshness.display_name,
    google_monitoring_alert_policy.high_rejection.display_name,
  ]
}
