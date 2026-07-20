variable "project_id" {
  type = string
}

variable "name_prefix" {
  type        = string
  description = "Prefix for metric/alert names, e.g. scb-dev."
}

variable "notification_email" {
  type        = string
  description = "Alert email. Empty disables the notification channel (alerts still exist)."
  default     = ""
}

variable "freshness_hours" {
  type        = number
  description = "Alert if no successful pipeline run within this many hours."
  default     = 26 # a daily batch + a few hours grace
}

variable "rejected_rows_threshold" {
  type        = number
  description = "Alert when a batch rejects more than this many rows."
  default     = 500
}
