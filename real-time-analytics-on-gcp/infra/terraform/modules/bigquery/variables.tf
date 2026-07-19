variable "project_id" {
  type = string
}

variable "bq_location" {
  type        = string
  description = "BigQuery dataset location. 'US' (multi-region) by default for availability; pin to a single region if data residency requires it."
  default     = "US"
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "uat", "prod"], var.environment)
    error_message = "environment must be one of: dev, uat, prod."
  }
}

variable "dataflow_worker_sa_email" {
  type = string
}

variable "bq_transform_sa_email" {
  type        = string
  description = "Output of the iam module — runs the Bronze -> Silver scheduled MERGE queries."
}

variable "looker_studio_viewers" {
  type        = list(string)
  description = "IAM members (e.g. \"user:you@example.com\") granted read access to the Gold dataset for Looker Studio dashboards."
  default     = []
}
