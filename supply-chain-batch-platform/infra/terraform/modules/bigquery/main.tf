# Creates BigQuery datasets and tables from JSON schema files that live next to
# this module (schemas/<logical>/<table>.json). Tables are auto-discovered, so
# adding a table = dropping a JSON file (metadata-driven, ADR-0005). Partitioning
# and clustering are supplied per table via var.table_options.

locals {
  schema_files = fileset("${path.module}/schemas", "**/*.json")

  # "gold/dim_material.json" -> key "gold/dim_material"
  tables = {
    for f in local.schema_files :
    trimsuffix(f, ".json") => {
      logical   = dirname(f)                       # "gold" | "metadata"
      table_id  = basename(trimsuffix(f, ".json")) # "dim_material"
      file_path = "${path.module}/schemas/${f}"
    }
  }
}

resource "google_bigquery_dataset" "this" {
  for_each = var.datasets

  project       = var.project_id
  dataset_id    = each.value.dataset_id
  friendly_name = each.value.dataset_id
  description   = each.value.description
  location      = var.location
  labels        = var.labels

  # Non-prod convenience: allow destroy of datasets with tables.
  delete_contents_on_destroy = var.delete_contents_on_destroy
}

resource "google_bigquery_table" "this" {
  for_each = local.tables

  project             = var.project_id
  dataset_id          = google_bigquery_dataset.this[each.value.logical].dataset_id
  table_id            = each.value.table_id
  schema              = file(each.value.file_path)
  deletion_protection = var.deletion_protection
  labels              = var.labels

  dynamic "time_partitioning" {
    for_each = try(var.table_options[each.key].partition_field, null) != null ? [1] : []
    content {
      type  = "DAY"
      field = var.table_options[each.key].partition_field
    }
  }

  clustering = try(var.table_options[each.key].clustering, null)
}
