variable "billing_account" {
  type        = string
  description = "Billing account id (e.g. 000000-AAAAAA-BBBBBB)."
}

variable "project_number" {
  type        = string
  description = "Numeric project number the budget scopes to."
}

variable "display_name" {
  type        = string
  description = "Budget display name."
  default     = "scb-dev-budget"
}

variable "amount" {
  type        = number
  description = "Budget amount in whole currency units."
  default     = 50
}

variable "currency" {
  type        = string
  description = "Currency code."
  default     = "USD"
}

variable "thresholds" {
  type        = list(number)
  description = "Alert threshold fractions of the budget."
  default     = [0.5, 0.9, 1.0]
}

variable "notification_channels" {
  type        = list(string)
  description = "Monitoring notification channel ids (optional). Mutually exclusive with pubsub_topic."
  default     = []
}

variable "pubsub_topic" {
  type        = string
  description = "Optional Pub/Sub topic for programmatic budget alerts (enterprise auto-disable pattern)."
  default     = null
}
