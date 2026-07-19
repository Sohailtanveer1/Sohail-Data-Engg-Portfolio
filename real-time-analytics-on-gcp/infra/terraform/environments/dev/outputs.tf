output "vpc_network_name" {
  value = module.networking.network_name
}

output "dataflow_worker_sa_email" {
  value = module.iam.dataflow_worker_sa_email
}

output "pubsub_bridge_sa_email" {
  value = module.iam.pubsub_bridge_sa_email
}

output "cicd_deployer_sa_email" {
  value = module.iam.cicd_deployer_sa_email
}

output "workload_identity_provider_name" {
  value = module.iam.workload_identity_provider_name
}

output "dataflow_staging_bucket" {
  value = module.storage.staging_bucket_name
}

output "raw_archive_bucket" {
  value = module.storage.raw_archive_bucket_name
}

output "pubsub_topic_ids" {
  value = module.pubsub.topic_ids
}

output "pubsub_subscription_names" {
  value = module.pubsub.subscription_names
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

output "carrier_api_key_secret_id" {
  value = module.secret_manager.carrier_api_key_secret_id
}
