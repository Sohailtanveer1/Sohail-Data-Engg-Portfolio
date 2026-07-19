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
  description = "Output of the iam module — granted reader on the image repo so the launcher/workers can pull the pipeline image."
}
