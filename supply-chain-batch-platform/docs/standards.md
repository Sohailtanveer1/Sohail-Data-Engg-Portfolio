# Standards: Git, Naming, Coding

Conventions every contributor (and future-you in an interview) can rely on.

---

## 1. Git branching strategy

**Trunk-based with short-lived feature branches + environment promotion via CI.**

- `main` — always deployable, **protected** (PR + green CI required, no direct push).
- `feature/<phase>-<short-desc>` — e.g. `feature/06-silver-scd2`. Short-lived,
  squash-merged.
- `fix/<desc>`, `docs/<desc>`, `chore/<desc>` — same rules.
- **Environment promotion is not a branch** — the same `main` artifact is
  promoted `dev → uat → prod` by CI applying the matching `*.tfvars`
  (avoids long-lived divergent env branches). ([ADR-0008](adr/0008-terraform-environments.md))
- **Tags/releases:** `vMAJOR.MINOR.PATCH` at milestone completion.

**Commit style:** Conventional Commits — `feat:`, `fix:`, `docs:`, `refactor:`,
`test:`, `chore:`, `ci:`. Imperative, scoped, e.g. `feat(silver): add SCD2 merge`.

---

## 2. Naming conventions

**Prefix:** `scb` = *Supply Chain Batch*. **Env:** `dev|uat|prod`.

| Resource | Pattern | Example |
|---|---|---|
| GCP project | `scb-<purpose>-<env>` | `scb-platform-dev` |
| GCS bucket (globally unique) | `scb-<projectid>-<env>-<layer>` | `scb-platform-dev-landing`, `-bronze`, `-silver`, `-gold`, `-archive`, `-temp` |
| BigQuery dataset | `scb_<layer>_<env>` | `scb_gold_dev`, `scb_metadata_dev` |
| BigQuery table (gold) | `dim_<x>` / `fact_<x>` | `dim_material`, `fact_shipment` |
| Service account | `scb-<component>-<env>` | `scb-dataproc-dev`, `scb-composer-dev`, `scb-ci-deployer` |
| Secret | `scb-<source>-<cred>` | `scb-sap-sftp-password`, `scb-salesforce-token` |
| Dataproc batch | `scb-<layer>-<entity>-<batchid>` | `scb-silver-material-20260719` |
| Airflow DAG id | `scb_<domain>_<cadence>` | `scb_sap_daily`, `scb_wms_4h` |
| Spark app / job file | `<layer>_<entity>.py` | `silver_material.py` |
| VPC / subnet | `scb-<env>-vpc` / `scb-<env>-subnet-<region>` | `scb-dev-vpc` |
| Terraform module | lowercase noun | `networking`, `storage`, `iam` |

**Column conventions:** `snake_case`; keys `*_id` (business) / `*_sk`
(surrogate); timestamps `*_ts` (UTC); dates `*_date`; audit columns
`batch_id`, `source_file`, `ingest_ts`, `row_hash`, `effective_from/to`,
`is_current`.

---

## 3. Python / PySpark coding standards

- **Python 3.11+**, type hints everywhere, docstrings on public functions.
- **Format:** `black`. **Lint:** `ruff`. **Imports:** `ruff`/`isort`.
  **Types:** `mypy` (strict-ish on `common/`).
- **Structure:** business logic in pure, testable functions; Spark I/O at the
  edges. No logic in DAGs — DAGs orchestrate, they don't transform.
- **Config over code:** no hard-coded paths/tables/creds — read from `config/` +
  environment + Secret Manager.
- **Logging:** structured JSON via the `common` logger. Every pipeline log carries
  the envelope: `pipeline`, `batch_id`, `source`, `destination`, `rows_read`,
  `rows_written`, `rows_rejected`, `duration_s`, `status`, `error`.
- **PySpark:** prefer DataFrame API over RDDs; avoid `collect()` on big data;
  explicit schemas (never `inferSchema` in production paths); broadcast small
  dims; name and reuse cached datasets; write partitioned, compacted output.
- **Idempotency:** every write is re-runnable (MERGE or partition overwrite keyed
  by `batch_id`/business key). No blind appends.
- **Errors:** typed exceptions, ret/retry with backoff for transient I/O, fail
  fast + audit for data errors.

---

## 4. SQL (BigQuery) standards

- Uppercase keywords, `snake_case` identifiers, leading commas optional but
  consistent, CTEs over nested subqueries.
- Partition facts by date; cluster by common filter keys (warehouse, material).
- Every model documents its **grain** in a header comment.
- Set **maximum bytes billed** on ad-hoc queries.

---

## 5. Terraform standards

- `terraform fmt` + `validate` + `tflint` in CI; `plan` on PR, `apply` on merge.
- Reusable modules in `modules/`; environments compose them with `*.tfvars`.
- Remote state (GCS), one prefix per env, state locking on.
- Variables typed + described + defaulted where safe; every module has
  `variables.tf`, `outputs.tf`, `main.tf`, `README.md`.
- No resource created outside Terraform (except the bootstrap state bucket).
- Cost-risky resources (`composer`) behind `enable_*` flags, **default false**.

---

## 6. Documentation standards

- Every folder has a `README.md` (purpose, contents, phase populated).
- Every major decision gets an **ADR** (`docs/adr/NNNN-title.md`).
- Every implementation section covers: business reasoning, architecture, code,
  testing, monitoring, security, cost, scalability, common mistakes, interview
  questions (the project's teaching contract).
- `PROJECT_PROGRESS.md` updated at the end of every phase.
