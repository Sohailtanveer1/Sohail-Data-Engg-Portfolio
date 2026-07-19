# Bootstrap: creates the GCS bucket that every environment's Terraform
# remote state lives in, plus enables the project APIs Terraform itself
# needs to touch before any other module can run.
#
# This uses a LOCAL backend deliberately — you can't store state for "the
# bucket that stores state" inside that same bucket (chicken-and-egg). Run
# this once per GCP project, by hand, before touching environments/*.
#
# terraform init && terraform apply
# (state file lands in infra/terraform/bootstrap/terraform.tfstate — see the
#  .gitignore note in this directory before committing anything.)

terraform {
  required_version = ">= 1.7.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
    # google-beta is required only for google_project_service_identity below —
    # the BigQuery Data Transfer Service agent isn't in the GA provider's
    # supported-services list for that resource.
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.30"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "required" {
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "compute.googleapis.com",
    "pubsub.googleapis.com",
    "dataflow.googleapis.com",
    "bigquery.googleapis.com",
    "bigquerydatatransfer.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "serviceusage.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Explicitly create the BigQuery Data Transfer Service agent so it exists
# before any environment's bigquery module tries to grant it
# serviceAccountTokenCreator (that grant fails with "service account does
# not exist" otherwise — a Google-managed identity that isn't auto-created
# until first use). Creating it here, in bootstrap, means the dependency is
# satisfied before any `environments/*` apply runs — codifying the manual
# `gcloud beta services identity create` step so uat/prod never hit it.
resource "google_project_service_identity" "bigquery_data_transfer" {
  provider = google-beta
  project  = var.project_id
  service  = "bigquerydatatransfer.googleapis.com"

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket" "tf_state" {
  name     = "${var.project_id}-tfstate"
  location = var.region
  project  = var.project_id

  # State history is how you recover from a bad apply — versioning is not
  # optional for a bucket that holds the only record of what Terraform
  # thinks exists.
  versioning {
    enabled = true
  }

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      num_newer_versions = 20
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.required]
}
