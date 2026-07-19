variable "project_id" {
  type        = string
  description = "GCP project id."
}

variable "region" {
  type        = string
  description = "Region for the state bucket."
  default     = "us-central1"
}

variable "state_bucket_prefix" {
  type        = string
  description = "Globally-unique prefix for the state bucket, e.g. scb-<projectid>."
}

variable "ci_deployer_roles" {
  type        = list(string)
  description = "Curated least-privilege roles for the CI deployer SA."
  default = [
    "roles/serviceusage.serviceUsageAdmin",
    "roles/storage.admin",
    "roles/compute.networkAdmin",
    "roles/iam.serviceAccountAdmin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/secretmanager.admin",
    "roles/bigquery.admin",
    "roles/dataproc.admin",
    "roles/composer.admin",
    "roles/monitoring.admin",
  ]
}
