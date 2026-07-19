variable "project_id" {
  description = "GCP project ID to bootstrap (the one holding your free-trial credits)."
  type        = string
}

variable "region" {
  description = "Default region for the state bucket."
  type        = string
  default     = "us-central1"
}
