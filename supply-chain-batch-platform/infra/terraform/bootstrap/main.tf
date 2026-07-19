# Bootstrap: the prerequisites every environment needs before it can run.
#   1) the versioned GCS bucket that holds remote state
#   2) the CI deployer service account that pipelines use to run Terraform
# Applied once, manually, with your own high-privilege identity.

resource "google_project_service" "bootstrap" {
  for_each = toset([
    "storage.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# --- Remote state bucket ---------------------------------------------------
resource "google_storage_bucket" "tfstate" {
  project                     = var.project_id
  name                        = "${var.state_bucket_prefix}-tfstate"
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  force_destroy               = false # protect state — never auto-delete

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 20
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.bootstrap]
}

# --- CI deployer service account ------------------------------------------
resource "google_service_account" "ci_deployer" {
  project      = var.project_id
  account_id   = "scb-ci-deployer"
  display_name = "SCB CI/CD Terraform deployer"
  depends_on   = [google_project_service.bootstrap]
}

# Roles the deployer needs to manage the platform stack. Curated (not Owner) so
# the CI identity is least-privilege. Phase 10 wires GitHub Actions to this SA via
# Workload Identity Federation (no exported keys).
resource "google_project_iam_member" "ci_deployer_roles" {
  for_each = toset(var.ci_deployer_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.ci_deployer.email}"
}

# Let the deployer read/write the state bucket.
resource "google_storage_bucket_iam_member" "ci_state_access" {
  bucket = google_storage_bucket.tfstate.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.ci_deployer.email}"
}
