output "airflow_uri" {
  description = "Airflow web UI URL (empty when disabled)."
  value       = var.enable ? google_composer_environment.this[0].config[0].airflow_uri : ""
}

output "dag_gcs_prefix" {
  description = "GCS path where DAGs are synced (empty when disabled)."
  value       = var.enable ? google_composer_environment.this[0].config[0].dag_gcs_prefix : ""
}
