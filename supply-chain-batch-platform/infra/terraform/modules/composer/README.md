# Module: composer

Cloud Composer 2 (managed Airflow). **Guarded** — `count = 0` unless
`enable = true`, so it is never created by accident (ADR-0003).

**Inputs:** `enable`, `project_id`, `region`, `name_prefix`, `network`,
`subnetwork`, `service_account`, `pods_range_name`, `services_range_name`,
`image_version`, `environment_size`, `pypi_packages`, `env_variables`.
**Outputs:** `airflow_uri`, `dag_gcs_prefix`.

> ⚠️ **Cost:** ~$10–15/day, no scale-to-zero. Create in Phase 8 (`enable=true` in
> tfvars), deploy DAGs to `dag_gcs_prefix`, and **`terraform destroy` this module
> between multi-day breaks**. The $50 budget alert is the backstop.

Runs on the private subnet with no external IPs; uses the `composer` service
account and the `composer-pods`/`composer-services` secondary ranges from the
networking module.
