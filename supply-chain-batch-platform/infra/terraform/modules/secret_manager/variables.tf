variable "project_id" {
  type        = string
  description = "GCP project id."
}

variable "name_prefix" {
  type        = string
  description = "Secret id prefix, e.g. scb-dev (secret becomes scb-dev-<name>)."
}

variable "secret_names" {
  type        = list(string)
  description = "Logical secret names to create (values added out-of-band)."
  default     = []
}

variable "accessors" {
  type = list(object({
    secret = string
    member = string
  }))
  description = "secretAccessor grants: which member can read which secret."
  default     = []
}

variable "labels" {
  type        = map(string)
  description = "Labels applied to every secret."
  default     = {}
}
