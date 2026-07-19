locals {
  environment       = "prod"
  dataflow_job_name = "supplychain-streaming-${local.environment}"
}

module "networking" {
  source      = "../../modules/networking"
  project_id  = var.project_id
  region      = var.region
  environment = local.environment
  subnet_cidr = var.subnet_cidr
}

module "iam" {
  source            = "../../modules/iam"
  project_id        = var.project_id
  environment       = local.environment
  github_repository = var.github_repository
}

module "storage" {
  source                   = "../../modules/storage"
  project_id               = var.project_id
  region                   = var.region
  environment              = local.environment
  dataflow_worker_sa_email = module.iam.dataflow_worker_sa_email
}

module "pubsub" {
  source                   = "../../modules/pubsub"
  project_id               = var.project_id
  environment              = local.environment
  dataflow_worker_sa_email = module.iam.dataflow_worker_sa_email
  pubsub_bridge_sa_email   = module.iam.pubsub_bridge_sa_email
}

module "bigquery" {
  source                   = "../../modules/bigquery"
  project_id               = var.project_id
  bq_location              = var.bq_location
  environment              = local.environment
  dataflow_worker_sa_email = module.iam.dataflow_worker_sa_email
  bq_transform_sa_email    = module.iam.bq_transform_sa_email
  looker_studio_viewers    = var.looker_studio_viewers
}

module "dataflow" {
  source                   = "../../modules/dataflow"
  project_id               = var.project_id
  region                   = var.region
  environment              = local.environment
  dataflow_worker_sa_email = module.iam.dataflow_worker_sa_email
}

module "secret_manager" {
  source                   = "../../modules/secret_manager"
  project_id               = var.project_id
  environment              = local.environment
  dataflow_worker_sa_email = module.iam.dataflow_worker_sa_email
}

module "monitoring" {
  source                             = "../../modules/monitoring"
  project_id                         = var.project_id
  environment                        = local.environment
  alert_email                        = var.alert_email
  subscription_names                 = module.pubsub.subscription_names
  dlq_monitoring_subscription_names  = module.pubsub.dlq_monitoring_subscription_names
  dataflow_job_name                  = local.dataflow_job_name
  backlog_threshold                  = var.backlog_threshold
  freshness_threshold_seconds        = var.freshness_threshold_seconds
  latency_threshold_seconds          = var.latency_threshold_seconds
}
