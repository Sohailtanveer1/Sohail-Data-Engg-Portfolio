# Partial backend: bucket/prefix supplied at init time so the name isn't hardcoded.
#   terraform init -backend-config=backend.hcl
# (backend.hcl is git-ignored; see backend.hcl.example)
terraform {
  backend "gcs" {}
}
