# UAT environment values. Fill project_id and billing_account with your own.
project_id      = "scb-platform-uat"
region          = "us-central1"
env             = "uat"
billing_account = "000000-AAAAAA-BBBBBB"

subnet_cidr            = "10.30.0.0/20"
composer_pods_cidr     = "10.40.0.0/16"
composer_services_cidr = "10.41.0.0/20"

budget_amount         = 50
force_destroy_buckets = true
