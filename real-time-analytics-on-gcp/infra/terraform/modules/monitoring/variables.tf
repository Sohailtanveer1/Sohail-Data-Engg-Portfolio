variable "project_id" {
  type = string
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "uat", "prod"], var.environment)
    error_message = "environment must be one of: dev, uat, prod."
  }
}

variable "alert_email" {
  type        = string
  description = "Where alert notifications go."
}

variable "subscription_names" {
  type        = map(string)
  description = "Output of the pubsub module — domain -> Dataflow subscription name."
}

variable "dlq_monitoring_subscription_names" {
  type        = map(string)
  description = "Output of the pubsub module — domain -> DLQ monitoring subscription name."
}

variable "dataflow_job_name" {
  type        = string
  description = "Name of the running streaming Dataflow job (see dataflow module)."
}

variable "backlog_threshold" {
  type        = number
  default     = 1000
  description = "num_undelivered_messages above which the pipeline is considered behind."
}

variable "freshness_threshold_seconds" {
  type    = number
  default = 300
}

variable "latency_threshold_seconds" {
  type    = number
  default = 120
}

variable "enable_logbased_metric_alerts" {
  type        = bool
  default     = false
  description = "Gates the two alert policies that reference log-based metrics (Dataflow errors, BigQuery write failures). Keep false until the streaming pipeline has run at least once — Cloud Monitoring rejects an alert policy on a log-based metric it has never seen data for. Flip to true and re-apply after RUNBOOK Step 9."
}
