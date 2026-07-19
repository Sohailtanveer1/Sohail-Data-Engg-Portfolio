variable "project_id" {
  type        = string
  description = "GCP project id."
}

variable "location" {
  type        = string
  description = "Bucket location (region for portfolio, e.g. us-central1)."
}

variable "bucket_prefix" {
  type        = string
  description = "Globally-unique bucket name prefix, e.g. scb-<projectid>-dev."
}

variable "force_destroy" {
  type        = bool
  description = "Allow `terraform destroy` to delete non-empty buckets (true in non-prod)."
  default     = false
}

variable "labels" {
  type        = map(string)
  description = "Labels applied to every bucket."
  default     = {}
}

variable "iam_members" {
  type = list(object({
    bucket = string
    role   = string
    member = string
  }))
  description = "Per-bucket least-privilege IAM bindings."
  default     = []
}
