# .github/workflows/

GitHub Actions CI/CD. **Implemented in Phase 10.**

- **`ci.yml`** (every PR/push): `python` job (black --check · ruff · mypy · pytest,
  94 tests), `terraform` matrix (fmt-check + init/validate on bootstrap+dev/uat/prod),
  `dags` job (Airflow DagBag import validation).
- **`cd-dev.yml`**: keyless deploy via **Workload Identity Federation** —
  `terraform plan` on PR, `apply` on merge to `main`, then rsync DAGs to Composer.

Local parity via [`.pre-commit-config.yaml`](../../.pre-commit-config.yaml). Full
walkthrough + required secrets: [docs/phase-10-cicd.md](../../docs/phase-10-cicd.md).
