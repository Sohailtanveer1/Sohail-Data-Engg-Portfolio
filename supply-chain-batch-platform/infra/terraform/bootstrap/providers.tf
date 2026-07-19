terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.45"
    }
  }
  # Local backend on purpose: bootstrap creates the remote-state bucket that every
  # other config uses (chicken-and-egg). Commit bootstrap state to a safe place or
  # keep it local; it changes rarely. terraform.tfstate here is git-ignored.
}

provider "google" {
  project = var.project_id
  region  = var.region
}
