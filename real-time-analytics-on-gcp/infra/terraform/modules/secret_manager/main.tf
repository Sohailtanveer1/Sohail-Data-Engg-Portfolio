# Secret Manager holds application secrets the pipeline needs at runtime —
# NOT service account keys (those should be Workload Identity / ADC where
# possible; see the iam module's WIF setup for the CI/CD case). The
# concrete secret here is a third-party carrier tracking API key used by
# the Beam pipeline's shipment-enrichment transform
# (dataflow/transforms/enrich_shipment.py).
#
# Terraform provisions the secret CONTAINER and a placeholder version only.
# The real value is set out-of-band (gcloud secrets versions add, or the
# console) specifically so it never passes through `terraform plan` output,
# state file, or a CI log.

resource "google_secret_manager_secret" "carrier_api_key" {
  project   = var.project_id
  secret_id = "carrier-tracking-api-key-${var.environment}"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "carrier_api_key_placeholder" {
  secret      = google_secret_manager_secret.carrier_api_key.id
  secret_data = "REPLACE_ME_VIA_GCLOUD_NOT_TERRAFORM"

  lifecycle {
    # Terraform creates version 1 as an inert placeholder; every real
    # rotation after that happens via `gcloud secrets versions add` and
    # Terraform is told to stop caring so a real secret value never ends
    # up in a plan/state diff.
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_iam_member" "dataflow_worker_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.carrier_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.dataflow_worker_sa_email}"
}
