variable "project_id" {
  type        = string
  description = "GCP project ID."
}

variable "region" {
  type        = string
  description = "Region for the subnet, router, and NAT."
}

variable "environment" {
  type        = string
  description = "dev, uat, or prod — used in resource naming."
  validation {
    condition     = contains(["dev", "uat", "prod"], var.environment)
    error_message = "environment must be one of: dev, uat, prod."
  }
}

variable "subnet_cidr" {
  type        = string
  description = "CIDR range for the subnet Dataflow workers run in."
  default     = "10.10.0.0/20"
}
