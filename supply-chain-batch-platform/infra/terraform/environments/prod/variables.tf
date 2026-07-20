variable "project_id" {
  type        = string
  description = "GCP project id for the dev environment."
}

variable "region" {
  type        = string
  description = "Primary region."
  default     = "us-central1"
}

variable "env" {
  type        = string
  description = "Environment short name."
  default     = "dev"
}

variable "billing_account" {
  type        = string
  description = "Billing account id for the budget."
}

variable "subnet_cidr" {
  type        = string
  description = "Primary private subnet CIDR."
  default     = "10.10.0.0/20"
}

variable "composer_pods_cidr" {
  type        = string
  description = "Secondary range for Composer/GKE pods."
  default     = "10.20.0.0/16"
}

variable "composer_services_cidr" {
  type        = string
  description = "Secondary range for Composer/GKE services."
  default     = "10.21.0.0/20"
}

variable "budget_amount" {
  type        = number
  description = "Budget alert amount (USD)."
  default     = 50
}

variable "force_destroy_buckets" {
  type        = bool
  description = "Allow destroy of non-empty buckets (true in dev)."
  default     = true
}

variable "bigquery_location" {
  type        = string
  description = "BigQuery dataset location."
  default     = "US"
}

variable "bigquery_deletion_protection" {
  type        = bool
  description = "Block destroy of BigQuery tables (true in prod)."
  default     = false
}
