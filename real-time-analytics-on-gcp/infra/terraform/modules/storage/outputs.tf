output "staging_bucket_name" {
  value = google_storage_bucket.dataflow_staging.name
}

output "staging_bucket_url" {
  value = google_storage_bucket.dataflow_staging.url
}

output "raw_archive_bucket_name" {
  value = google_storage_bucket.raw_archive.name
}
