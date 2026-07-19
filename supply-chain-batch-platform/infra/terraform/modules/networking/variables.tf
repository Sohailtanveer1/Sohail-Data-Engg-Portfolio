variable "project_id" {
  type        = string
  description = "GCP project id."
}

variable "region" {
  type        = string
  description = "Region for the subnet, router, and NAT."
}

variable "name_prefix" {
  type        = string
  description = "Resource name prefix, e.g. scb-dev."
}

variable "subnet_cidr" {
  type        = string
  description = "Primary private subnet CIDR."
  default     = "10.10.0.0/20"
}

variable "secondary_ranges" {
  type = list(object({
    range_name    = string
    ip_cidr_range = string
  }))
  description = "Secondary ranges for Composer 2 / GKE (pods, services)."
  default     = []
}

variable "enable_iap_ssh" {
  type        = bool
  description = "Allow SSH from Google's IAP range (for debugging only)."
  default     = false
}
