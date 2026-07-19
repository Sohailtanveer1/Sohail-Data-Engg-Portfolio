# One dedicated service account per component, each granted only the project-level
# roles it needs (least privilege). Bucket-level and secret-level grants live in
# the storage / secret_manager modules; cross-SA actAs bindings live in the root.

resource "google_service_account" "this" {
  for_each = var.service_accounts

  project      = var.project_id
  account_id   = "${var.name_prefix}-${each.key}"
  display_name = each.value.display_name
}

# Flatten {sa => [roles]} into (sa, role) pairs for individual bindings.
locals {
  sa_role_pairs = merge([
    for sa_key, sa in var.service_accounts : {
      for role in sa.project_roles : "${sa_key}:${role}" => {
        sa_key = sa_key
        role   = role
      }
    }
  ]...)
}

resource "google_project_iam_member" "roles" {
  for_each = local.sa_role_pairs

  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.this[each.value.sa_key].email}"
}
