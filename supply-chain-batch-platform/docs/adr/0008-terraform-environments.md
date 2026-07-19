# ADR-0008 — Terraform layout & environment isolation

**Status:** Proposed · **Date:** 2026-07-19

## Context
Everything must be Terraform-provisioned, isolated across `dev`/`uat`/`prod`,
support clean `apply`/`destroy` with no orphans, and keep cost-risky resources
from being created by accident.

## Options
1. **Single root, workspaces for envs.** Less duplication, but one blast radius
   and easy to apply to the wrong env.
2. **Per-environment directories composing shared modules.** ✅ Clear isolation,
   independent state, explicit per-env `*.tfvars`.
3. **Terragrunt.** Powerful DRY, but extra tooling/learning overhead not needed here.

## Decision
**Option 2.** `infra/terraform/modules/` holds reusable modules;
`infra/terraform/environments/{dev,uat,prod}/` compose them with per-env
`*.tfvars`. **Remote state** in a versioned GCS bucket, one **prefix per env**,
with state locking. A `bootstrap/` config creates the state bucket + CI deployer
SA (the pre-requisite layer). Cost-risky modules (`composer`) are behind
`enable_*` flags defaulting to **false**. Non-prod buckets use `force_destroy`
so `destroy` leaves no orphans.

## Consequences
- ➕ Strong env isolation; blast radius contained to one env.
- ➕ `apply`/`destroy` round-trips cleanly; verified in Phase 3.
- ➕ Accidental Composer creation is impossible without flipping a flag.
- ➖ Some config duplication across env dirs (acceptable, explicit).
- ➖ Bootstrap chicken-and-egg handled by a separate one-time apply.

## Enterprise vs Portfolio
- **Enterprise:** CI/CD-only applies, policy-as-code (OPA/Sentinel), Terragrunt
  or a platform layer, per-env projects/folders, CMEK.
- **Portfolio:** per-env dirs + GCS backend + GitHub Actions `plan`/`apply`,
  `force_destroy` on non-prod.
