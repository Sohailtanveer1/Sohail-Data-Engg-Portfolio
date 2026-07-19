# Service account IDENTITIES + the handful of roles that are genuinely
# project-scoped (a worker reporting its own job status/logs/metrics has no
# narrower resource to scope that to). Every resource-specific grant
# (BigQuery dataset access, a Pub/Sub subscription, a Secret Manager secret)
# is bound in the module that owns that resource, taking this SA's email as
# an input — that way "what can the Dataflow worker touch" is answered by
# reading the bigquery/pubsub/secret_manager modules, not by hunting through
# a single monolithic IAM file.

resource "google_service_account" "dataflow_worker" {
  project      = var.project_id
  account_id   = "sa-dataflow-worker-${var.environment}"
  display_name = "Dataflow worker (${var.environment}) — least-privilege, no owner/editor"
}

resource "google_service_account" "pubsub_bridge" {
  project      = var.project_id
  account_id   = "sa-pubsub-bridge-${var.environment}"
  display_name = "Kafka-to-Pub/Sub bridge (${var.environment}) — runs outside GCP"
}

resource "google_service_account" "cicd_deployer" {
  project      = var.project_id
  account_id   = "sa-cicd-deployer-${var.environment}"
  display_name = "GitHub Actions Terraform deployer (${var.environment}) — auth via Workload Identity Federation, no static key"
}

resource "google_service_account" "bq_transform" {
  project      = var.project_id
  account_id   = "sa-bq-transform-${var.environment}"
  display_name = "BigQuery scheduled queries (${var.environment}) — runs the Bronze->Silver MERGE jobs"
}

# Roles a Dataflow worker needs regardless of which pipeline it's running:
# to exist as a worker at all (dataflow.worker) and to write its own
# operational telemetry. Data-plane access (BigQuery, Pub/Sub, Secret
# Manager) is granted per-resource elsewhere.
resource "google_project_iam_member" "dataflow_worker_roles" {
  for_each = toset([
    "roles/dataflow.worker",
    "roles/monitoring.metricWriter",
    "roles/logging.logWriter",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.dataflow_worker.email}"
}

# The deployer needs broad create/manage permissions because Terraform
# itself provisions IAM, networking, and every data resource in this
# project — see docs/security-guide.md for the trade-off discussion
# (a real org would scope this per-environment or front it with a
# just-in-time elevation workflow rather than a standing broad grant).
resource "google_project_iam_member" "cicd_deployer_roles" {
  for_each = toset([
    "roles/compute.networkAdmin",
    "roles/compute.securityAdmin",
    "roles/iam.serviceAccountAdmin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/storage.admin",
    "roles/pubsub.admin",
    "roles/bigquery.admin",
    "roles/dataflow.admin",
    "roles/secretmanager.admin",
    "roles/monitoring.admin",
    "roles/logging.admin",
    "roles/serviceusage.serviceUsageAdmin",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.cicd_deployer.email}"
}

# --- Workload Identity Federation for GitHub Actions -----------------------
# No JSON key ever leaves GCP. GitHub's OIDC token is exchanged for a
# short-lived GCP access token, scoped to this one repo via the attribute
# condition below — a leaked Actions log can't be replayed as a standing
# credential the way a static SA key could.

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-actions-pool-${var.environment}"
  display_name              = "GitHub Actions (${var.environment})"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # Restricts token exchange to THIS repo only — swap in your actual
  # org/repo before applying.
  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_actions_wif" {
  service_account_id = google_service_account.cicd_deployer.name
  role                = "roles/iam.workloadIdentityUser"
  member              = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}
