# Cloud Composer 2 (managed Airflow). GUARDED: count=0 unless enable=true, so it
# is never created by accident (ADR-0003). This is the project's largest cost
# (~$10-15/day, no scale-to-zero) — create in Phase 8, DESTROY between breaks.

resource "google_composer_environment" "this" {
  count   = var.enable ? 1 : 0
  project = var.project_id
  name    = "${var.name_prefix}-composer"
  region  = var.region

  config {
    environment_size = var.environment_size

    software_config {
      image_version = var.image_version
      pypi_packages = var.pypi_packages
      env_variables = var.env_variables
    }

    node_config {
      network         = var.network
      subnetwork      = var.subnetwork
      service_account = var.service_account

      ip_allocation_policy {
        cluster_secondary_range_name  = var.pods_range_name
        services_secondary_range_name = var.services_range_name
      }
    }

    # Smallest viable workloads to keep cost down.
    workloads_config {
      scheduler {
        cpu        = 0.5
        memory_gb  = 2
        storage_gb = 1
        count      = 1
      }
      web_server {
        cpu        = 0.5
        memory_gb  = 2
        storage_gb = 1
      }
      worker {
        cpu        = 0.5
        memory_gb  = 2
        storage_gb = 1
        min_count  = 1
        max_count  = 2
      }
    }
  }
}
