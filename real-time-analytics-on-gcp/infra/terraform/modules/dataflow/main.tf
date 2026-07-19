# Deliberately does NOT provision the streaming Dataflow job itself as a
# Terraform resource (google_dataflow_flex_template_job exists, but
# streaming jobs are a poor fit for Terraform's plan/apply model — an
# in-place pipeline code change usually needs a `--update` job replacement
# that Terraform's provider handles inconsistently, and drift detection on
# a long-running streaming job is noisy). Terraform's job here is the
# durable infra a job launch depends on; the job itself is launched
# imperatively by scripts/deploy_dataflow_pipeline.sh, called from CI/CD
# (see .github/workflows/cd-dev.yml) — same split any team running
# streaming Dataflow in production converges on.

resource "google_artifact_registry_repository" "dataflow_images" {
  project       = var.project_id
  location      = var.region
  repository_id = "supplychain-dataflow-${var.environment}"
  format        = "DOCKER"
  description   = "Flex Template container images for the streaming pipeline."

  cleanup_policies {
    id     = "keep-last-10"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }

  cleanup_policies {
    id     = "delete-older-than-90d"
    action = "DELETE"
    condition {
      older_than = "7776000s" # 90 days
    }
  }
}

# The Flex Template launcher VM and the workers both run as the Dataflow
# worker SA and must PULL the pipeline image from this repo — without
# reader access the launch dies at "artifactregistry.repositories.
# downloadArtifacts denied" before the job graph is ever built. (Cloud
# Build has separate push access via its own SA; this is the read side.)
resource "google_artifact_registry_repository_iam_member" "worker_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.dataflow_images.location
  repository = google_artifact_registry_repository.dataflow_images.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${var.dataflow_worker_sa_email}"
}
