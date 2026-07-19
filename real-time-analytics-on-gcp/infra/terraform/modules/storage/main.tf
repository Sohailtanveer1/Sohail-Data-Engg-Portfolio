# Two buckets, two different jobs:
# - staging: Dataflow's own working directory (JAR/package staging, temp
#   shuffle spill for batch, pipeline options). Short-lived content only.
# - raw_archive: every raw event, written by the pipeline as a secondary
#   sink alongside BigQuery Bronze. This is the actual replay/backfill
#   source of truth — BigQuery Bronze can be dropped and rebuilt from here,
#   but Kafka retention (7-14 days) cannot cover a 6-month-old backfill
#   request, and this bucket can.

resource "google_storage_bucket" "dataflow_staging" {
  project                     = var.project_id
  name                        = "${var.project_id}-dataflow-staging-${var.environment}"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = var.environment != "prod"

  lifecycle_rule {
    condition { age = 7 }
    action    { type = "Delete" }
  }
}

resource "google_storage_bucket" "raw_archive" {
  project                     = var.project_id
  name                        = "${var.project_id}-raw-event-archive-${var.environment}"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = var.environment != "prod"

  versioning {
    enabled = var.environment == "prod"
  }

  # Raw events are cheap to store and expensive to lose (they're the
  # ultimate replay source) — age out to cheaper storage classes instead
  # of deleting.
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }
}

resource "google_storage_bucket_iam_member" "dataflow_worker_staging" {
  bucket = google_storage_bucket.dataflow_staging.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.dataflow_worker_sa_email}"
}

resource "google_storage_bucket_iam_member" "dataflow_worker_archive" {
  bucket = google_storage_bucket.raw_archive.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.dataflow_worker_sa_email}"
}
