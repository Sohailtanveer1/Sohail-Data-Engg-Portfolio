output "state_bucket_name" {
  value       = google_storage_bucket.tf_state.name
  description = "Reference this in each environment's backend.tf"
}
