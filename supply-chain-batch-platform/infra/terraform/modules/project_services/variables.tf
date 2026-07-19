variable "project_id" {
  type        = string
  description = "GCP project id in which to enable services."
}

variable "services" {
  type        = list(string)
  description = "List of service APIs to enable (e.g. compute.googleapis.com)."
}
