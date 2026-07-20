# modules/

Reusable Terraform modules (each with `main.tf`, `variables.tf`, `outputs.tf`,
`README.md`).

**Built:** `project_services`, `networking`, `iam`, `secret_manager`, `storage`,
`budget` (Phase 3); `bigquery` (Phase 4); `composer` (Phase 8, guarded);
`monitoring` (Phase 9).

**Note:** there is no `dataproc` module — Spark runs as **Dataproc Serverless
batches** submitted by Airflow (ADR-0002), so there's no cluster to Terraform.

Composed per environment under `../environments/{dev,uat,prod}/`. See
[ADR-0008](../../../docs/adr/0008-terraform-environments.md) and the
[Phase 3 walkthrough](../../../docs/phase-03-terraform-foundation.md).
