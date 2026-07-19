output "state_bucket" {
  description = "Name of the remote-state bucket. Use it in each env's backend.tf."
  value       = google_storage_bucket.tfstate.name
}

output "ci_deployer_email" {
  description = "CI deployer service-account email (used by GitHub Actions in Phase 10)."
  value       = google_service_account.ci_deployer.email
}
