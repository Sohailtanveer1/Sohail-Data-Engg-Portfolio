output "bronze_dataset_id" {
  value = google_bigquery_dataset.bronze.dataset_id
}

output "silver_dataset_id" {
  value = google_bigquery_dataset.silver.dataset_id
}

output "gold_dataset_id" {
  value = google_bigquery_dataset.gold.dataset_id
}

output "bronze_table_ids" {
  value = { for d, t in google_bigquery_table.bronze : d => t.table_id }
}

output "silver_table_ids" {
  value = { for d, t in google_bigquery_table.silver : d => t.table_id }
}

output "gold_view_ids" {
  value = { for d, t in google_bigquery_table.gold_views : d => t.table_id }
}
