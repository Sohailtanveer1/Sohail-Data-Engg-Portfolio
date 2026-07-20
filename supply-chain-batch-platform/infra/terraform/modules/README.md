# modules/

Reusable Terraform modules (each with `main.tf`, `variables.tf`, `outputs.tf`,
`README.md`).

**Built:** `project_services`, `networking`, `iam`, `secret_manager`, `storage`,
`budget` (Phase 3); `bigquery` (Phase 4).

**Coming:** `dataproc` (Phase 6), `composer` (Phase 8), `monitoring` (Phase 9).

Composed per environment under `../environments/{dev,uat,prod}/`. See
[ADR-0008](../../../docs/adr/0008-terraform-environments.md) and the
[Phase 3 walkthrough](../../../docs/phase-03-terraform-foundation.md).
