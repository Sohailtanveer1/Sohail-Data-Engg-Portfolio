variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "bq_location" {
  type    = string
  default = "US"
}

variable "subnet_cidr" {
  type    = string
  default = "10.11.0.0/20" # distinct range from dev (10.10.0.0/20) — see docs/architecture/network-diagram.md
}

variable "github_repository" {
  type = string
}

variable "alert_email" {
  type = string
}

variable "looker_studio_viewers" {
  type    = list(string)
  default = []
}

variable "backlog_threshold" {
  type    = number
  default = 2000 # UAT runs load/soak tests — a higher baseline avoids alert noise during intentional bursts
}
