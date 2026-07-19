output "vpc_network_name" {
  value = module.networking.network_name
}

output "dataflow_worker_sa_email" {
  value = module.iam.dataflow_worker_sa_email
}

output "cicd_deployer_sa_email" {
  value = module.iam.cicd_deployer_sa_email
}

output "workload_identity_provider_name" {
  value = module.iam.workload_identity_provider_name
}

output "bigquery_datasets" {
  value = {
    bronze = module.bigquery.bronze_dataset_id
    silver = module.bigquery.silver_dataset_id
    gold   = module.bigquery.gold_dataset_id
  }
}

output "dataflow_artifact_registry_repo" {
  value = module.dataflow.artifact_registry_repo_url
}
