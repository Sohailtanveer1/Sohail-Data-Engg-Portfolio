# Dev environment root — composes the shared modules (ADR-0008). Same modules will
# form uat/prod with different tfvars. Cost-risky compute (Dataproc/Composer) is
# added in Phases 6/8; Phase 3 lays the foundation only.

data "google_project" "this" {
  project_id = var.project_id
}

locals {
  name_prefix   = "scb-${var.env}"                   # scb-dev
  bucket_prefix = "scb-${var.project_id}-${var.env}" # globally unique
  labels = {
    platform = "supply-chain-batch"
    env      = var.env
    managed  = "terraform"
  }
}

module "project_services" {
  source     = "../../modules/project_services"
  project_id = var.project_id
  services = [
    "compute.googleapis.com",
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "dataproc.googleapis.com",
    "composer.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudbilling.googleapis.com",
    "artifactregistry.googleapis.com",
  ]
}

module "networking" {
  source      = "../../modules/networking"
  project_id  = var.project_id
  region      = var.region
  name_prefix = local.name_prefix
  subnet_cidr = var.subnet_cidr
  secondary_ranges = [
    { range_name = "composer-pods", ip_cidr_range = var.composer_pods_cidr },
    { range_name = "composer-services", ip_cidr_range = var.composer_services_cidr },
  ]
  enable_iap_ssh = false

  depends_on = [module.project_services]
}

module "iam" {
  source      = "../../modules/iam"
  project_id  = var.project_id
  name_prefix = local.name_prefix

  service_accounts = {
    dataproc = {
      display_name = "SCB Dataproc (Spark) - ${var.env}"
      project_roles = [
        "roles/dataproc.worker",
        "roles/bigquery.dataEditor",
        "roles/bigquery.jobUser",
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
      ]
    }
    composer = {
      display_name = "SCB Composer (Airflow) - ${var.env}"
      project_roles = [
        "roles/composer.worker",
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
      ]
    }
    ingestion = {
      display_name = "SCB Ingestion (extractors) - ${var.env}"
      project_roles = [
        "roles/logging.logWriter",
      ]
    }
  }

  depends_on = [module.project_services]
}

# Composer must be able to run tasks as the Dataproc SA (submit Spark batches).
resource "google_service_account_iam_member" "composer_actas_dataproc" {
  service_account_id = module.iam.ids["dataproc"]
  role               = "roles/iam.serviceAccountUser"
  member             = module.iam.members["composer"]
}

module "storage" {
  source        = "../../modules/storage"
  project_id    = var.project_id
  location      = var.region
  bucket_prefix = local.bucket_prefix
  force_destroy = var.force_destroy_buckets
  labels        = local.labels

  iam_members = [
    # Ingestion writes raw drops into landing/archive.
    { bucket = "landing", role = "roles/storage.objectAdmin", member = module.iam.members["ingestion"] },
    { bucket = "archive", role = "roles/storage.objectAdmin", member = module.iam.members["ingestion"] },
    # Dataproc reads landing, and owns bronze/silver/gold + scratch.
    { bucket = "landing", role = "roles/storage.objectViewer", member = module.iam.members["dataproc"] },
    { bucket = "bronze", role = "roles/storage.objectAdmin", member = module.iam.members["dataproc"] },
    { bucket = "silver", role = "roles/storage.objectAdmin", member = module.iam.members["dataproc"] },
    { bucket = "gold", role = "roles/storage.objectAdmin", member = module.iam.members["dataproc"] },
    { bucket = "temp", role = "roles/storage.objectAdmin", member = module.iam.members["dataproc"] },
    { bucket = "dataproc-staging", role = "roles/storage.objectAdmin", member = module.iam.members["dataproc"] },
  ]

  depends_on = [module.project_services]
}

module "secret_manager" {
  source      = "../../modules/secret_manager"
  project_id  = var.project_id
  name_prefix = local.name_prefix
  labels      = local.labels

  secret_names = [
    "sap-sftp-password",
    "salesforce-token",
    "wms-db-password",
  ]

  accessors = [
    { secret = "sap-sftp-password", member = module.iam.members["ingestion"] },
    { secret = "salesforce-token", member = module.iam.members["ingestion"] },
    { secret = "wms-db-password", member = module.iam.members["ingestion"] },
  ]

  depends_on = [module.project_services]
}

module "budget" {
  source          = "../../modules/budget"
  billing_account = var.billing_account
  project_number  = data.google_project.this.number
  display_name    = "${local.name_prefix}-budget"
  amount          = var.budget_amount
  thresholds      = [0.5, 0.9, 1.0]

  depends_on = [module.project_services]
}

module "bigquery" {
  source              = "../../modules/bigquery"
  project_id          = var.project_id
  location            = var.bigquery_location
  labels              = local.labels
  deletion_protection = var.bigquery_deletion_protection

  datasets = {
    metadata = {
      dataset_id  = "scb_metadata_${var.env}"
      description = "Control / audit / watermark / DQ / schema-registry tables"
    }
    gold = {
      dataset_id  = "scb_gold_${var.env}"
      description = "Kimball star schema (conformed dims + facts) served to Looker"
    }
  }

  # Partition facts by their event date; cluster by common filter keys. Metadata
  # audit tables partition by their timestamp so retention/queries stay cheap.
  table_options = {
    "gold/fact_purchase_order"      = { partition_field = "order_date", clustering = ["material_sk", "warehouse_sk"] }
    "gold/fact_goods_receipt"       = { partition_field = "receipt_date", clustering = ["material_sk", "warehouse_sk"] }
    "gold/fact_inventory_snapshot"  = { partition_field = "snapshot_date", clustering = ["warehouse_sk", "material_sk"] }
    "gold/fact_stock_movement"      = { partition_field = "movement_date", clustering = ["material_sk", "warehouse_sk"] }
    "gold/fact_inventory_valuation" = { partition_field = "valuation_date", clustering = ["material_sk", "warehouse_sk"] }
    "gold/fact_shipment"            = { partition_field = "ship_date", clustering = ["carrier_sk", "origin_warehouse_sk"] }
    "metadata/batch_audit"          = { partition_field = "started_at", clustering = ["pipeline", "status"] }
    "metadata/file_audit"           = { partition_field = "seen_at", clustering = ["source", "checksum"] }
    "metadata/dq_results"           = { partition_field = "at", clustering = ["entity", "rule"] }
  }

  depends_on = [module.project_services]
}
