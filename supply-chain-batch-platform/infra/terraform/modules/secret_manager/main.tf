# Creates the platform secrets (container only — values are injected out-of-band,
# never in Terraform state) and grants accessor to the SAs that need them.

resource "google_secret_manager_secret" "this" {
  for_each = toset(var.secret_names)

  project   = var.project_id
  secret_id = "${var.name_prefix}-${each.value}"

  replication {
    auto {}
  }

  labels = var.labels
}

# Grant secretAccessor to specified members per secret.
resource "google_secret_manager_secret_iam_member" "accessors" {
  for_each = { for a in var.accessors : "${a.secret}:${a.member}" => a }

  project   = var.project_id
  secret_id = google_secret_manager_secret.this[each.value.secret].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value.member
}
