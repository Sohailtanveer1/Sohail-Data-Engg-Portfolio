output "dataflow_worker_sa_email" {
  value = google_service_account.dataflow_worker.email
}

output "pubsub_bridge_sa_email" {
  value = google_service_account.pubsub_bridge.email
}

output "cicd_deployer_sa_email" {
  value = google_service_account.cicd_deployer.email
}

output "bq_transform_sa_email" {
  value = google_service_account.bq_transform.email
}

output "workload_identity_provider_name" {
  value       = google_iam_workload_identity_pool_provider.github.name
  description = "Full resource name to put in the GitHub Actions workflow's workload_identity_provider input."
}
