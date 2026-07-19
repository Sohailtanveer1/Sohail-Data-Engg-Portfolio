# Development Roadmap & Milestones

Eleven phases, each self-contained and reviewable, each following the 15-step
teaching structure. **We stop for your review at the end of every phase.**
Live status lives in [PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).

---

## Milestones

| Milestone | Phases | "Done" looks like |
|---|---|---|
| **M0 — Plan approved** | 1 | This document set reviewed & approved |
| **M1 — Local platform runs** | 2 | `docker compose up` gives Postgres, mock SF API, SFTP, local Airflow, local Spark; generators emit data for all 5 sources |
| **M2 — Cloud foundation live (dev)** | 3–4 | `terraform apply` stands up network, IAM, buckets, secrets, BigQuery datasets + metadata/control/audit tables |
| **M3 — Data lands & flows to Silver** | 5–6 | All 5 sources land to Bronze; Spark builds validated, deduped, SCD Silver (Iceberg) |
| **M4 — Gold serves BigQuery** | 7 | Star schema (facts + dims) populated in BigQuery, queryable |
| **M5 — Orchestrated end-to-end** | 8 | Airflow DAGs run the full daily batch with sensors, retries, SLAs; Composer demo captured |
| **M6 — Trustworthy & observed** | 9 | DQ framework enforcing rules; monitoring, alerts, structured logs, audit tables populated |
| **M7 — Automated & tested** | 10 | CI/CD green: format, lint, unit/integration/e2e tests, `terraform plan`, DAG validation |
| **M8 — Delivered** | 11 | Looker dashboards, DR plan, full docs, HANDBOOK/RUNBOOK, cleanup verified |

---

## Phase-by-phase

### Phase 1 — Planning & Architecture *(current)*
Architecture, data model, ADRs, roadmap, standards, cost, risk. **No code.**
Exit: your approval.

### Phase 2 — Local development environment
- `data_generators/` for all 5 sources (realistic + deliberately messy rows).
- `local/docker-compose.yml`: Postgres (WMS), mock Salesforce REST API, SFTP
  server, local Airflow, local Spark.
- `common/` Python package skeleton: structured logging, config loader, schema &
  DQ primitives, metadata helpers. Packaged + unit-tested.
- Runs entirely local, **$0 GCP**.

### Phase 3 — Terraform foundation (dev)
- `bootstrap/`: remote-state bucket + CI deployer SA.
- Modules: `project_services`, `networking`, `iam`, `secret_manager`, `storage`,
  plus a $50 billing budget.
- Deploy to `dev`. Prove `apply`/`destroy` round-trip.

### Phase 4 — BigQuery datasets & metadata model
- `bigquery` module: `*_gold` and `*_metadata` datasets.
- DDL for control/audit/watermark/DQ/schema-registry tables + Gold dims/facts.
- Free-tier only.

### Phase 5 — Ingestion (land → Bronze)
- Per-source extractors (SFTP, REST, JDBC, GCS) → landing bucket.
- Metadata-driven: `config/` YAML drives which entities load and how.
- File tracking, checksums, idempotent landing, archive strategy, Bronze Parquet.

### Phase 6 — Spark Bronze → Silver
- Schema validation & evolution, typing, dedup, DQ gate, quarantine.
- SCD1 & SCD2 with Iceberg `MERGE INTO`; idempotent, late-arriving handling.
- Iceberg catalog + runtime-jar setup on local Spark and Dataproc Serverless
  (documented as a reproducible runbook step).
- Local Spark for dev; Dataproc Serverless for scale runs. Spark tuning topics
  (partitioning, broadcast, AQE, skew, small files) demonstrated here.

### Phase 7 — Gold (dimensional model → BigQuery)
- Build conformed dims + facts from Silver; surrogate keys; load to BigQuery.
- Semi-additive handling for inventory snapshots.

### Phase 8 — Orchestration (Airflow → real Cloud Composer)
- DAG design, dynamic DAGs from metadata, task groups, sensors, branching,
  retries, SLAs, pools, XCom, trigger rules.
- Develop DAGs on local Airflow, then deploy to a **real Cloud Composer 2**
  environment (Terraform, `enable_composer=true`). Destroy Composer between
  multi-day breaks to control cost (ADR-0003).

### Phase 9 — Data quality, monitoring, logging
- Harden the reusable DQ framework (all rule types).
- Cloud Logging structured logs, log-based metrics, alert policies, freshness &
  failure monitoring, audit dashboards.

### Phase 10 — CI/CD & testing
- GitHub Actions: format (black/ruff), lint, mypy, pytest (unit/integration),
  Spark tests, DAG validation, `terraform fmt/validate/plan`, deploy to dev.

### Phase 11 — Serve, harden, hand off
- Looker Studio dashboards on Gold.
- Disaster-recovery plan, troubleshooting guide, runbook, HANDBOOK.
- Final cost review + cleanup verification.

---

## Sequencing rationale
We build **inside-out**: local first ($0, fast feedback), then cloud foundation,
then data flow bottom-up (Bronze→Silver→Gold), then orchestration wraps it,
then quality/observability hardens it, then CI/CD automates it, then we serve and
document. Each phase produces something demonstrable and independently defensible
in an interview.
