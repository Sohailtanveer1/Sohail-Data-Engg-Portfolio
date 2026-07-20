# Setup Guide

New here? Two paths, both in the [RUNBOOK](../RUNBOOK.md).

## Local ($0) — recommended first
```bash
python -m venv .venv && . .venv/Scripts/activate      # PS: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt && pip install -e common -e data_generators
pytest -q                                             # 94 tests should pass
python -m data_generators.generate --source all --date 2026-07-19
python -m ingestion.run --source sap_erp --date 2026-07-19
```
Full local flow (Docker stack, Spark, dim_date): [RUNBOOK §A](../RUNBOOK.md#a-local-everything-0).

## GCP dev
Prereqs: a Free-Trial project, `gcloud` + `terraform`, `gcloud auth
application-default login`. Then follow [RUNBOOK §B](../RUNBOOK.md#b-gcp-dev)
(bootstrap → foundation → secrets → Gold views).

## Tooling versions
Python 3.11/3.12 (Spark needs ≤3.12 + a JDK) · Terraform ≥1.5 · Docker Desktop ·
`gcloud`. Pinned dev tools in [requirements-dev.txt](../requirements-dev.txt).
