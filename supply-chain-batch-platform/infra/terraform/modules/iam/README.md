# Module: iam

Creates one dedicated service account per component and grants each only the
project-level roles it needs (least privilege).

**Inputs:** `project_id`, `name_prefix`, `service_accounts` (map of short name ->
`{display_name, project_roles}`).
**Outputs:** `emails`, `members`, `ids` (maps keyed by short name).

Bucket-level IAM is granted in the `storage` module and secret-accessor grants in
`secret_manager`, using the `members` output here. Cross-SA `actAs`
(`roles/iam.serviceAccountUser`, e.g. Composer → Dataproc SA) is wired in the
environment root. Typical SAs: `dataproc`, `composer`, `ingestion`.
