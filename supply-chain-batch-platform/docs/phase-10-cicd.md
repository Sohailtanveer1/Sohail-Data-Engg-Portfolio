# Phase 10 — CI/CD & Testing

> The 15-step walkthrough for the automated quality gate: GitHub Actions running
> format, lint, type-check, the full test suite, Terraform validate, and Airflow
> DAG validation on every PR — plus a keyless deploy to dev.

---

## 1. Objectives

Turn the 94 tests + Terraform + DAGs into an **automated gate**: nothing merges
unless it's formatted, linted, typed, tested, and valid; deploy to dev keylessly.

## 2. Theory

- **Fail fast on every PR.** Format/lint/type/test run before human review.
- **Trunk-based + plan-on-PR / apply-on-merge.** PRs show a Terraform `plan`;
  merges to `main` `apply` — the promotion model from ADR-0008.
- **Keyless deploy (Workload Identity Federation).** GitHub authenticates to GCP
  via OIDC — **no exported service-account keys** (the #1 CI credential leak).
- **DAG validation is a test.** Importing the DAGs in CI catches broken DAGs
  before they reach Composer.

## 3. Business Context

A platform a team relies on can't depend on people remembering to run checks. CI
is the contract: green means safe. Keyless deploy means a repo compromise doesn't
hand out long-lived GCP credentials.

## 4. Architecture

```
PR ─► CI (ci.yml)
      ├─ python    : black --check · ruff · mypy · pytest (94 tests)
      ├─ terraform : fmt -check + init/validate  [matrix: bootstrap, dev, uat, prod]
      └─ dags      : install Airflow (constrained) → DagBag import (no errors)

PR touching infra ─► CD plan (cd-dev.yml, WIF)     merge to main ─► CD apply + deploy DAGs
```

## 5. Folder Creation

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml),
[`.github/workflows/cd-dev.yml`](../.github/workflows/cd-dev.yml),
[`.pre-commit-config.yaml`](../.pre-commit-config.yaml).

## 6. Infrastructure

No new GCP infra. CD reuses the **bootstrap CI deployer SA** (Phase 3) via WIF and
the remote-state bucket. Composer DAG deploy only fires if Composer is enabled.

## 7. Implementation

- **`ci.yml`** — three parallel jobs (python 3.12, terraform matrix, dag-validation
  on 3.11 with Airflow constraints). `concurrency` cancels superseded runs.
- **`cd-dev.yml`** — `google-github-actions/auth` (OIDC), `terraform plan` on PR /
  `apply` on push, then `gcloud storage rsync` of DAGs to the Composer bucket. The
  `dev` GitHub Environment can require a reviewer for a manual approval gate.
- **`.pre-commit-config.yaml`** — mirrors CI locally (ruff, black, terraform_fmt,
  `detect-private-key`).

## 8. Testing / Verification

Run locally (the exact CI commands), all green:

| Gate | Result |
|---|---|
| `black --check .` | ✅ 64 files clean |
| `ruff check .` | ✅ all checks passed (51 issues fixed getting here) |
| `pytest -q` | ✅ **94 passed** |
| `terraform fmt -check -recursive` | ✅ clean |
| `terraform validate` (4 roots) | ✅ Success |
| Workflow + pre-commit YAML | ✅ valid |

> **mypy** couldn't run locally (this machine's Application Control policy blocks
> its compiled extension) — it runs in CI on Linux runners. Config is scoped to
> `common/scb_common` with `check_untyped_defs`.

## 9. Documentation

This doc + `.github/workflows` README + PROJECT_PROGRESS.

## 10. Code Review notes

- Ruff cleanup modernized the codebase (`datetime.UTC`, `collections.abc`, import
  sorting, `zip(strict=…)`) — all behavior-preserving; the 94 tests still pass.
- The Terraform job runs `fmt -check` once (guarded on the bootstrap matrix leg) to
  avoid four redundant tree-wide checks.
- CD `plan` uses `-out=tfplan` and `apply tfplan` so the applied plan is exactly
  the reviewed one.

## 11. Interview Questions

- *Why WIF over a service-account key?* No long-lived secret to leak/rotate; GitHub
  proves identity via short-lived OIDC tokens.
- *Why plan-on-PR, apply-on-merge?* Reviewers see the exact infra diff before it
  lands; merge applies the reviewed plan.
- *How do you catch a broken DAG before prod?* A CI job imports the DagBag and
  fails on any import error.
- *Why constrain the Airflow install?* Airflow's dependency tree is huge; the
  official constraints file pins a known-good set for reproducible CI.

## 12. Best Practices applied

CI on every PR; keyless deploy; plan/apply separation; DAG validation; pre-commit
parity; concurrency cancellation; matrix over Terraform roots; secret scanning.

## 13. Common Mistakes (avoided)

Exported SA keys in CI; applying un-reviewed plans; skipping DAG validation;
lint/format drift between local and CI; committing private keys (pre-commit guard).

## 14. Cost Considerations

**$0** — GitHub Actions free tier covers this; CD only spends when it applies real
infra (which stays within the Phase-3/8 cost posture, Composer still guarded).

## 15. Next Steps

**Phase 11 — Serve, harden, hand off:** Looker Studio dashboards on the Gold model,
a disaster-recovery plan, troubleshooting guide + runbook + HANDBOOK, a final cost
review, and the cleanup verification — the delivery phase.

---

## Run the gate locally

```bash
pip install -r requirements-dev.txt && pip install -e common
black --check . && ruff check . && mypy && pytest -q
terraform fmt -check -recursive infra/terraform
pre-commit install    # optional: run the gate on every commit
```
