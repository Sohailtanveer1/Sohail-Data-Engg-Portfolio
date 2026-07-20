output "bucket_names" {
  description = "Medallion + ops bucket names."
  value       = module.storage.bucket_names
}

output "service_account_emails" {
  description = "Component service-account emails."
  value       = module.iam.emails
}

output "network" {
  description = "VPC and subnet identifiers."
  value = {
    network = module.networking.network_name
    subnet  = module.networking.subnet_name
  }
}

output "secret_ids" {
  description = "Created secret ids (values added out-of-band)."
  value       = module.secret_manager.secret_ids
}

output "project_number" {
  value = data.google_project.this.number
}

output "bigquery_datasets" {
  description = "Created BigQuery dataset ids."
  value       = module.bigquery.dataset_ids
}

output "composer_airflow_uri" {
  description = "Airflow UI URL (empty unless enable_composer=true)."
  value       = module.composer.airflow_uri
}

output "composer_dag_prefix" {
  description = "GCS prefix to deploy DAGs to (empty unless enabled)."
  value       = module.composer.dag_gcs_prefix
}
