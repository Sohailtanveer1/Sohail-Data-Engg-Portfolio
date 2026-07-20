# Dev environment values. Fill project_id and billing_account with your own.
project_id      = "scb-platform-dev"
region          = "us-central1"
env             = "dev"
billing_account = "000000-AAAAAA-BBBBBB"

# Networking
subnet_cidr            = "10.10.0.0/20"
composer_pods_cidr     = "10.20.0.0/16"
composer_services_cidr = "10.21.0.0/20"

# Cost controls
budget_amount         = 50
force_destroy_buckets = true

# Orchestration (ADR-0003): flip to true in Phase 8, then destroy between breaks.
enable_composer = false
