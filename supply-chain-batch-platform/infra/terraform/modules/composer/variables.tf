variable "enable" {
  type        = bool
  description = "Create Composer only when true. Default false (cost guard, ADR-0003)."
  default     = false
}

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "network" {
  type        = string
  description = "VPC self-link/id from the networking module."
}

variable "subnetwork" {
  type        = string
  description = "Private subnet self-link/id."
}

variable "service_account" {
  type        = string
  description = "Composer runtime service-account email."
}

variable "pods_range_name" {
  type        = string
  description = "Secondary range name for GKE pods."
  default     = "composer-pods"
}

variable "services_range_name" {
  type        = string
  description = "Secondary range name for GKE services."
  default     = "composer-services"
}

variable "image_version" {
  type        = string
  description = "Composer/Airflow image, e.g. composer-2.9.7-airflow-2.9.3."
  default     = "composer-2.9.7-airflow-2.9.3"
}

variable "environment_size" {
  type    = string
  default = "ENVIRONMENT_SIZE_SMALL"
}

variable "pypi_packages" {
  type        = map(string)
  description = "Extra PyPI packages (name -> version spec)."
  default     = {}
}

variable "env_variables" {
  type        = map(string)
  description = "Airflow environment variables."
  default     = {}
}
