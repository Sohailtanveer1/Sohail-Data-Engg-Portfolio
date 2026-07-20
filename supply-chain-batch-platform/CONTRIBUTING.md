# Contributing

## Setup

```bash
python -m venv .venv && . .venv/Scripts/activate        # PS: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt && pip install -e common -e data_generators
pre-commit install         # runs the gate on every commit
```

## The quality gate (must pass — CI enforces it)

```bash
black --check .        # format
ruff check .           # lint
mypy                   # types (common/scb_common)
pytest -q              # 94 tests
terraform fmt -check -recursive infra/terraform
```

## Conventions

- **Branches:** `feature/<phase>-<desc>`, `fix/<desc>`, `docs/<desc>`; short-lived,
  squash-merged. `main` is protected (PR + green CI).
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`,
  `ci:`), imperative and scoped.
- **Code:** type hints + docstrings; business logic in pure/testable functions,
  I/O at the edges; config over code (no hard-coded paths/tables/secrets);
  structured logging with the `batch_id` envelope. See [docs/standards.md](docs/standards.md).
- **Onboarding a source/entity:** add a `config/` entry (and a schema/DQ block for
  Silver) — not new code, where possible (ADR-0005).

## Adding a new…

| Thing | How |
|---|---|
| Source entity (ingest) | add to `config/sources/<source>.yaml` |
| Silver entity | add `config/silver/<entity>.yaml` (schema + DQ + SCD) |
| Gold fact | add `config/gold/<entity>.yaml` (dims + measures) |
| BigQuery table | drop a JSON schema in `infra/terraform/modules/bigquery/schemas/` |
| DQ rule type | add to `scb_common/dq.py` + `rule_to_condition` in `spark/transforms/expressions.py` |
| Terraform module | `infra/terraform/modules/<name>/` with `main/variables/outputs/README` |

## Never commit

Secrets, SA keys, `.env`, real `terraform.tfvars`/`backend.hcl`, `*.tfstate`,
generated `data/`. `.gitignore` + pre-commit `detect-private-key` guard these.

## PR checklist

- [ ] Gate passes locally · [ ] tests added/updated · [ ] docs/ADR updated if a
  decision changed · [ ] `PROJECT_PROGRESS.md` touched if a phase advanced.
