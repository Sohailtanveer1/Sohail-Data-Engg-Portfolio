output "topic_ids" {
  value = { for d, t in google_pubsub_topic.domain : d => t.id }
}

output "dlq_topic_ids" {
  value = { for d, t in google_pubsub_topic.domain_dlq : d => t.id }
}

output "subscription_ids" {
  value = { for d, s in google_pubsub_subscription.domain_dataflow : d => s.id }
}

output "subscription_names" {
  value = { for d, s in google_pubsub_subscription.domain_dataflow : d => s.name }
}

output "dlq_monitoring_subscription_names" {
  value = { for d, s in google_pubsub_subscription.domain_dlq_monitoring : d => s.name }
}
