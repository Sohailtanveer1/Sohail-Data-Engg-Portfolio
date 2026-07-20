variable "project_id" {
  type        = string
  description = "GCP project id."
}

variable "location" {
  type        = string
  description = "BigQuery dataset location (e.g. US or us-central1)."
  default     = "US"
}

variable "datasets" {
  type = map(object({
    dataset_id  = string
    description = string
  }))
  description = "Logical name (matches schema subfolder) -> dataset config."
}

variable "table_options" {
  type = map(object({
    partition_field = optional(string)
    clustering      = optional(list(string))
  }))
  description = "Per-table partition/cluster options, keyed by \"<logical>/<table>\"."
  default     = {}
}

variable "deletion_protection" {
  type        = bool
  description = "Block `terraform destroy` from deleting tables (true in prod)."
  default     = false
}

variable "delete_contents_on_destroy" {
  type        = bool
  description = "Allow destroying datasets that still contain tables (true in non-prod)."
  default     = true
}

variable "labels" {
  type        = map(string)
  description = "Labels applied to datasets and tables."
  default     = {}
}
