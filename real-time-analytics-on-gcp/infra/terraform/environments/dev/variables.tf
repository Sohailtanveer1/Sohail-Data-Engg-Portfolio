variable "project_id" {
  type        = string
  description = "GCP project ID (your free-trial project)."
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "bq_location" {
  type    = string
  default = "US"
}

variable "subnet_cidr" {
  type    = string
  default = "10.10.0.0/20"
}

variable "github_repository" {
  type        = string
  description = "\"owner/repo\" allowed to deploy via Workload Identity Federation."
}

variable "alert_email" {
  type        = string
  description = "Where monitoring alerts are sent."
}

variable "looker_studio_viewers" {
  type    = list(string)
  default = []
}
