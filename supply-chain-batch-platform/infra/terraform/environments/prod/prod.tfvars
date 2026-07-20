# PROD environment values. Fill project_id and billing_account with your own.
# Note: force_destroy_buckets = false — production buckets are protected.
project_id      = "scb-platform-prod"
region          = "us-central1"
env             = "prod"
billing_account = "000000-AAAAAA-BBBBBB"

subnet_cidr            = "10.50.0.0/20"
composer_pods_cidr     = "10.60.0.0/16"
composer_services_cidr = "10.61.0.0/20"

budget_amount                = 100
force_destroy_buckets        = false
bigquery_deletion_protection = true
