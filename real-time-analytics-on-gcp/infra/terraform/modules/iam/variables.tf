variable "project_id" {
  type        = string
  description = "GCP project ID."
}

variable "environment" {
  type        = string
  description = "dev, uat, or prod."
  validation {
    condition     = contains(["dev", "uat", "prod"], var.environment)
    error_message = "environment must be one of: dev, uat, prod."
  }
}

variable "github_repository" {
  type        = string
  description = "GitHub repo allowed to assume the deployer SA via WIF, as \"owner/repo\"."
}
