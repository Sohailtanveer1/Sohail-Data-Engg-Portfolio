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
  default = "10.12.0.0/20" # distinct from dev (10.10.0.0/20) and uat (10.11.0.0/20)
}

variable "github_repository" {
  type = string
}

variable "alert_email" {
  type        = string
  description = "Should be an on-call rotation address/pager integration, not a single person's inbox."
}

variable "looker_studio_viewers" {
  type    = list(string)
  default = []
}

variable "backlog_threshold" {
  type    = number
  default = 500 # tighter than dev/uat — prod backlog growth should page sooner
}

variable "freshness_threshold_seconds" {
  type    = number
  default = 180
}

variable "latency_threshold_seconds" {
  type    = number
  default = 60
}
