output "dataset_ids" {
  description = "Map of logical name -> dataset_id."
  value       = { for k, d in google_bigquery_dataset.this : k => d.dataset_id }
}

output "table_ids" {
  description = "Fully-qualified table ids created."
  value       = { for k, t in google_bigquery_table.this : k => "${t.project}.${t.dataset_id}.${t.table_id}" }
}
