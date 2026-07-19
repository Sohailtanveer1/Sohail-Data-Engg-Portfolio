# Enables the GCP APIs the platform needs. Applied first — everything else
# depends on these being on. disable_on_destroy=false so a `destroy` of the
# stack does not rip APIs out from under other resources/projects.

resource "google_project_service" "this" {
  for_each = toset(var.services)

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
