# GCS buckets for the medallion lake + ops. Uniform bucket-level access (no ACLs),
# lifecycle tiering to control cost, and least-privilege bucket IAM.

locals {
  # Standard bucket set. lifecycle_age_days -> transition to Nearline (or delete
  # for temp). versioning kept on where accidental overwrite would hurt.
  buckets = {
    landing          = { lifecycle_age_days = 30, versioning = false, action = "SetStorageClass" }
    bronze           = { lifecycle_age_days = 60, versioning = false, action = "SetStorageClass" }
    silver           = { lifecycle_age_days = 0, versioning = true, action = "" }
    gold             = { lifecycle_age_days = 0, versioning = true, action = "" }
    archive          = { lifecycle_age_days = 30, versioning = false, action = "SetStorageClass" }
    temp             = { lifecycle_age_days = 7, versioning = false, action = "Delete" }
    dataproc-staging = { lifecycle_age_days = 14, versioning = false, action = "Delete" }
    artifacts        = { lifecycle_age_days = 0, versioning = true, action = "" }
  }
}

resource "google_storage_bucket" "this" {
  for_each = local.buckets

  project                     = var.project_id
  name                        = "${var.bucket_prefix}-${each.key}"
  location                    = var.location
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  force_destroy               = var.force_destroy
  labels                      = var.labels

  versioning {
    enabled = each.value.versioning
  }

  # Cost lifecycle: tier cold data to Nearline, or delete scratch buckets.
  dynamic "lifecycle_rule" {
    for_each = each.value.action == "SetStorageClass" ? [1] : []
    content {
      condition {
        age = each.value.lifecycle_age_days
      }
      action {
        type          = "SetStorageClass"
        storage_class = "NEARLINE"
      }
    }
  }

  dynamic "lifecycle_rule" {
    for_each = each.value.action == "Delete" ? [1] : []
    content {
      condition {
        age = each.value.lifecycle_age_days
      }
      action {
        type = "Delete"
      }
    }
  }
}

# Least-privilege, per-bucket IAM (e.g. ingestion SA writes landing; Dataproc SA
# reads/writes bronze/silver/gold/staging).
resource "google_storage_bucket_iam_member" "bindings" {
  for_each = { for b in var.iam_members : "${b.bucket}:${b.role}:${b.member}" => b }

  bucket = google_storage_bucket.this[each.value.bucket].name
  role   = each.value.role
  member = each.value.member
}
