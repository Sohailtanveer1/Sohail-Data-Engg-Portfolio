# Module: project_services

Enables the GCP APIs the platform depends on. Apply this before any other module.

**Inputs:** `project_id`, `services` (list of API names).
**Outputs:** `enabled_services`.

`disable_on_destroy = false` — destroying the stack does not disable the APIs
(prevents cascading failures and is friendlier on shared projects).
