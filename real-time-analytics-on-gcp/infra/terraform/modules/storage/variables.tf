variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "uat", "prod"], var.environment)
    error_message = "environment must be one of: dev, uat, prod."
  }
}

variable "dataflow_worker_sa_email" {
  type        = string
  description = "Output of the iam module — the SA the pipeline runs as."
}
