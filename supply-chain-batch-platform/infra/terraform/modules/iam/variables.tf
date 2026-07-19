variable "project_id" {
  type        = string
  description = "GCP project id."
}

variable "name_prefix" {
  type        = string
  description = "Service-account id prefix, e.g. scb-dev (account id becomes scb-dev-<key>)."
}

variable "service_accounts" {
  type = map(object({
    display_name  = string
    project_roles = list(string)
  }))
  description = "Component SAs keyed by short name (e.g. dataproc, composer, ingestion)."
}
