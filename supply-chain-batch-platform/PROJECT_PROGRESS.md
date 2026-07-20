# PROJECT_PROGRESS.md

Live phase tracker for the Supply Chain Batch Data Platform. Every phase follows
the same 15-step teaching structure (Objectives → Theory → Business Context →
Architecture → Folder Creation → Infrastructure → Implementation → Testing →
Documentation → Code Review → Interview Questions → Best Practices → Common
Mistakes → Cost Considerations → Next Steps).

**Legend:** ⬜ Not started · 🟨 In progress · ✅ Complete · ⏸️ Blocked / waiting

---

## Phase Overview

| Phase | Name | Status | Runs where | Est. GCP cost |
|---|---|---|---|---|
| 1 | Planning & Architecture | ✅ Approved | Local (docs only) | $0 |
| 2 | Local dev environment + data generators + `common` package | ✅ Complete | Local (Docker) | $0 |
| 3 | Terraform foundation: APIs, VPC/networking, IAM, buckets, Secret Manager | ✅ Complete | GCP dev | ~$0–1 |
| 4 | BigQuery: datasets + metadata/control/audit + Gold DDL | ✅ Complete | GCP dev | ~$0 (free tier) |
| 5 | Ingestion: land 5 sources → Bronze (metadata-driven, file tracking, archive) | ✅ Complete | Local + GCP | ~$1–3 |
| 6 | Spark Bronze→Silver: schema validation, DQ, dedup, SCD1/SCD2, idempotency | ✅ Complete | Local Spark + Dataproc Serverless | ~$2–5 |
| 7 | Gold build: dimensional model → BigQuery | ✅ Complete | Dataproc Serverless + BQ | ~$1–3 |
| 8 | Orchestration: Airflow DAGs → **Cloud Composer** (managed) | 🟨 In review | Local dev + Cloud Composer | ⚠️ ~$10–15/day while up |
| 9 | Data quality framework + monitoring/logging + alerts | ⬜ | GCP dev | ~$0–1 |
| 10 | CI/CD (GitHub Actions) + full test suite | ⬜ | GitHub | $0 |
| 11 | Looker Studio dashboards + DR + docs finalization + cleanup | ⬜ | GCP dev | $0 |

> ⚠️ **Cost sentinel:** Cloud Composer is the single biggest spend in this project
> (~$10–15/day, no scale-to-zero). **Decision (ADR-0003): we run a real Composer
> environment**, created in Phase 8 and **`terraform destroy`-ed between multi-day
> breaks**, then re-applied when resuming. DAGs are developed on local Airflow
> first to keep iteration fast. See [docs/cost-optimization.md](docs/cost-optimization.md).

---

## Phase 1 — Planning & Architecture — 🟨 In review

**Objective:** Produce a complete, defensible plan before writing any production code.

### Deliverables

- [x] Repository & folder structure scaffolded (READMEs in every folder)
- [x] System architecture — [docs/architecture/architecture-overview.md](docs/architecture/architecture-overview.md)
- [x] Data model (medallion + Kimball star) — [docs/architecture/data-model.md](docs/architecture/data-model.md)
- [x] Source-system analysis — [docs/source-systems.md](docs/source-systems.md)
- [x] Architecture Decision Records (ADR 0001–0010) — [docs/adr/](docs/adr/)
- [x] Terraform module plan — in architecture overview + ADR-0008
- [x] Development roadmap & milestones — [docs/roadmap.md](docs/roadmap.md)
- [x] Git branching strategy, naming conventions, coding standards — [docs/standards.md](docs/standards.md)
- [x] Cost estimation & GCP Free-Trial plan — [docs/cost-optimization.md](docs/cost-optimization.md)
- [x] Risk assessment — [docs/risk-assessment.md](docs/risk-assessment.md)

### Exit criteria

- [x] **User reviewed and approved the plan** (2026-07-19).
- [x] Requested changes incorporated (Iceberg, real Composer, full teaching depth).

**Cleanup checklist (Phase 1):** none — no billable resources created.

---

## Phase 2 — Local dev environment + generators + `common` — 🟨 In review

**Objective:** A laptop-only platform ($0 GCP) that emulates all five sources and
provides the shared library every later phase builds on. Full walkthrough:
[docs/phase-02-local-environment.md](docs/phase-02-local-environment.md).

### Deliverables

- [x] `scb_common` package: logging, config, batch context, schema contracts,
      DQ framework, retry, metadata/audit store — [common/scb_common/](common/scb_common/)
- [x] Five data generators (SAP/Salesforce/WMS/TMS/Supplier) with deliberate
      dirty-data injection — [data_generators/](data_generators/)
- [x] `generate.py` CLI writing native formats (CSV/JSON/Parquet/Excel + `_SUCCESS`)
- [x] Local Docker stack: Postgres (WMS), mock Salesforce REST API, SFTP —
      [local/docker-compose.yml](local/docker-compose.yml)
- [x] WMS seed script + local bootstrap scripts — [scripts/](scripts/)
- [x] **46 tests passing** (36 `common` + 7 generators + 3 integration)
- [x] Verified: full-source generation produces all native-format files on Py3.14

### Known/deferred

- Local **Airflow** (Phase 8) and **Spark** (Phase 6) are added when there are
  DAGs/jobs to run — an empty Airflow now would be noise.
- Live Docker bring-up not exercised in the authoring session (Docker Desktop
  daemon was not running); `compose config` validated and container scripts
  byte-compile. Run `scripts/bootstrap_local.ps1` to start it.

### Exit criteria

- [x] Phase 2 reviewed; approved to proceed.

**Cleanup checklist (Phase 2):** `docker compose -f local/docker-compose.yml down -v`
to stop containers and drop the Postgres volume. No GCP resources created ($0).

---

## Phase 3 — Terraform foundation (dev) — 🟨 In review

**Objective:** Provision the platform foundation (APIs, private networking,
least-privilege IAM, buckets, secrets, $50 budget) as reusable, env-isolated
Terraform. No compute yet. Walkthrough + apply runbook:
[docs/phase-03-terraform-foundation.md](docs/phase-03-terraform-foundation.md).

### Deliverables

- [x] 6 reusable modules: `project_services`, `networking`, `iam`,
      `secret_manager`, `storage`, `budget` — [infra/terraform/modules/](infra/terraform/modules/)
- [x] `bootstrap/` — remote-state bucket + CI deployer SA (local-state, one-time)
- [x] `environments/{dev,uat,prod}/` roots composing the modules (per-env tfvars)
- [x] Private networking (ADR-0009), least-privilege IAM, lifecycle buckets, $50 budget
- [x] **`terraform validate` = Success** on bootstrap/dev/prod roots; `fmt` clean

### Not done here (by design)

- **No `terraform apply`** in the authoring session — it needs your real GCP
  project + credentials and creates (tiny) billable resources. Follow the runbook
  in the phase doc to apply to your dev project.
- Dataproc/Composer/BigQuery modules come in Phases 4/6/8.

### Exit criteria

- [x] Phase 3 reviewed; approved to proceed.

**Cleanup checklist (Phase 3):** `terraform destroy -var-file=dev.tfvars` in
`environments/dev` (then optionally `bootstrap`). Verify ~$0 run-rate in Billing.
NAT is the only ongoing trickle (~$1–3/mo) and is destroyed with the stack.

---

## Phase 4 — BigQuery datasets, metadata model & Gold DDL — 🟨 In review

**Objective:** The serving (`scb_gold_<env>`) and operational (`scb_metadata_<env>`)
BigQuery layers, all Terraform-managed, plus a BigQuery backend for the metadata
store. Free-tier only. Walkthrough:
[docs/phase-04-bigquery-metadata.md](docs/phase-04-bigquery-metadata.md).

### Deliverables

- [x] Reusable `bigquery` module (auto-discovers JSON schemas, partition/cluster
      via `table_options`) — [infra/terraform/modules/bigquery/](infra/terraform/modules/bigquery/)
- [x] **20 tables**: 7 metadata (control/audit/watermark/DQ/schema-registry) +
      13 Gold (7 dims SCD1/SCD2 + 6 partitioned/clustered facts)
- [x] Wired into dev/uat/prod roots (prod: deletion protection on)
- [x] `BigQueryMetadataStore` (same interface as JSONL) —
      [common/scb_common/stores/bigquery.py](common/scb_common/stores/bigquery.py)
- [x] `terraform validate` Success on all roots; `fmt` clean; 20 schemas valid JSON
- [x] **52 tests passing** (+6 BigQuery-store tests via a fake backend)

### Not done here (by design)

- Tables are **created empty** — populated in Phases 5–7.
- No `terraform apply` in-session (needs your project); `bq ls` verification steps
  are in the phase doc's runbook addition.

### Exit criteria

- [x] Phase 4 reviewed; approved to proceed.

**Cleanup checklist (Phase 4):** covered by the dev `terraform destroy`
(`delete_contents_on_destroy=true` in non-prod). BigQuery cost is ~$0 (free tier).

---

## Phase 5 — Ingestion (land → Bronze) — 🟨 In review

**Objective:** Metadata-driven extractors that land all five sources to Bronze
Parquet with checksum dedup, watermark incremental, archive, and full audit.
Walkthrough: [docs/phase-05-ingestion.md](docs/phase-05-ingestion.md).

### Deliverables

- [x] `ingestion/` framework: `LandingStore` (local+GCS), format readers
      (CSV/JSON/Parquet/Excel), `jdbc.py`, `bronze.py`, `extractor.py`, `run.py`
- [x] `config/sources/*.yaml` for all five sources (metadata-driven)
- [x] Bronze contract: raw, string-typed, 7 audit columns, partitioned by ingest_date
- [x] Checksum idempotency, per-entity watermarks, archive, batch/file audit
- [x] **63 tests passing** (+11 ingestion)
- [x] **Real run verified**: 4 file-based sources → 14 Bronze files; re-run sap_erp
      → 5 skipped (idempotent); audit + watermarks written

### Known/deferred

- **WMS (JDBC)** path is implemented but not run in-session (needs the live
  Postgres from Phase 2; daemon was down). Run once the Docker stack is up.
- Salesforce connector reads the landed JSON payloads (same as the mock API
  serves); a live-HTTP-API variant is a documented extension.

### Exit criteria

- [x] Phase 5 reviewed; approved to proceed.

**Cleanup checklist (Phase 5):** local only — `rm -rf data/bronze data/_audit
data/archive` to reset. $0 GCP.

---

## Phase 6 — Spark Bronze → Silver (Iceberg, DQ, SCD) — 🟨 In review

**Objective:** PySpark/Iceberg transforms turning Bronze into typed, deduped,
quality-gated Silver with SCD1/SCD2 history, idempotently. Walkthrough:
[docs/phase-06-spark-silver.md](docs/phase-06-spark-silver.md).

### Deliverables

- [x] `spark/transforms/`: `expressions` (pure builders), `scd` (MERGE SQL),
      `dq_spark` (Spark gate reusing Phase-2 rules), `clean`, `session` (Iceberg+AQE)
- [x] `spark/jobs/silver_job.py` — config-driven Bronze→Silver orchestration
- [x] `config/silver/` — `material_master` (SCD2 dim) + `purchase_order` (fact)
- [x] **76 tests passing** (+13 Spark builder tests: casts, every rule's SQL,
      SCD1/SCD2 statements, DDL, dedup)
- [x] Cross-phase proof: real Bronze `purchase_order` (1238 rows) → **31
      quarantined** by the same DQ config that feeds the Spark gate
- [x] Spark modules `py_compile` clean

### Not done here (environment)

- **Spark not executed in-session:** no JDK installed and PySpark lacks Python
  3.14 support. Logic is pure-unit-tested; orchestration is compile-checked. Run
  via a local JDK + py3.12 venv, or Dataproc Serverless (both in the phase doc).

### Exit criteria

- [x] Phase 6 reviewed; approved to proceed (Spark execution deferred to user's JDK/Dataproc).

**Cleanup checklist (Phase 6):** local only — `rm -rf data/silver data/quarantine`.
Dataproc Serverless batches auto-terminate (no idle cost).

---

## Phase 7 — Gold: dimensional model → BigQuery — 🟨 In review

**Objective:** Build the conformed Kimball star from Silver (point-in-time SK
resolution, semi-additive handling) and load it to the Phase-4 BigQuery Gold
tables. Walkthrough: [docs/phase-07-gold.md](docs/phase-07-gold.md).

### Deliverables

- [x] `spark/transforms/gold.py` — pure builders: `generate_dim_date`,
      `pit_join_clause` (SCD2 as-of), `build_fact_select` (SK resolution + measures)
- [x] `spark/jobs/gold_job.py` — Silver→Gold→BigQuery (Spark-BQ connector)
- [x] `config/gold/fact_purchase_order.yaml` + `scripts/build_dim_date.py`
- [x] **81 tests passing** (+5 Gold)
- [x] **`dim_date` built for real** (1,461 rows, 4 fiscal years) — no Spark needed
- [x] `gold_job.py` compiles

### Not done here (environment)

- Fact build is Spark → same JDK/Dataproc constraint as Phase 6. Logic
  unit-tested; job compile-checked; `dim_date` runs standalone.

### Exit criteria

- [x] Phase 7 reviewed; approved to proceed.

**Cleanup checklist (Phase 7):** local `rm -rf data/gold`; BigQuery Gold covered by
`terraform destroy`. $0 (free tier + Serverless).

---

## Phase 8 — Orchestration (Airflow → Cloud Composer) — 🟨 In review

**Objective:** Wire the full daily batch into Airflow (dynamic-from-metadata,
sensors, task groups, pools, SLAs, trigger rules), develop locally, deploy to a
**real Cloud Composer** env (guarded). Walkthrough:
[docs/phase-08-orchestration.md](docs/phase-08-orchestration.md).

### Deliverables

- [x] Guarded `composer` Terraform module (`enable=false` default) + wired into
      all env roots behind `enable_composer`
- [x] `airflow/dags/dag_builder.py` — pure task-graph builder + acyclic guard
- [x] `airflow/dags/supply_chain_daily.py` — dynamic DAG (sensors → ingest →
      Silver/Gold Dataproc batches), TaskGroups, pools, SLAs, XCom, trigger rules
- [x] `airflow/plugins/scb/sensors.py` — reschedule-mode FileArrivalSensor
- [x] `airflow/docker-compose.airflow.yml` — local Airflow ($0 dev)
- [x] **87 tests passing** (+6 DAG builder); Airflow modules compile; Composer
      module `terraform validate` Success on all roots

### Not done here (environment/cost)

- Airflow not run in-session (Python 3.14). Run locally via the compose, or on Composer.
- **Composer not created** (`enable_composer=false`). Turn on deliberately per the
  runbook, then destroy between breaks (cost, ADR-0003).

### Exit criteria

- [ ] **User reviews Phase 8.** ← _we are here_

**Cleanup checklist (Phase 8):** `docker compose -f airflow/docker-compose.airflow.yml
down -v` (local). If Composer was enabled: `terraform apply -var enable_composer=false`.

---

## Decision Log (ADRs)

| ADR | Decision | Status |
|---|---|---|
| [0001](docs/adr/0001-medallion-storage-layout.md) | Bronze/Silver on GCS (Parquet), Gold in BigQuery | Proposed |
| [0002](docs/adr/0002-compute-dataproc-serverless.md) | Dataproc Serverless (+ local Spark) over persistent clusters | Proposed |
| [0003](docs/adr/0003-orchestration-airflow.md) | **Cloud Composer** (managed Airflow); local Airflow for dev | Proposed |
| [0004](docs/adr/0004-table-format-iceberg.md) | **Apache Iceberg** on GCS for Silver (ACID MERGE, evolution, BigQuery-readable) | Proposed |
| [0005](docs/adr/0005-metadata-driven-framework.md) | Config-driven pipelines with control/audit/watermark tables | Proposed |
| [0006](docs/adr/0006-scd-strategy.md) | SCD2 for dims that need history, SCD1 for the rest | Proposed |
| [0007](docs/adr/0007-incremental-idempotency.md) | Watermark incremental + idempotent MERGE/overwrite | Proposed |
| [0008](docs/adr/0008-terraform-environments.md) | Reusable modules + per-env dirs + remote GCS backend | Proposed |
| [0009](docs/adr/0009-networking.md) | Custom VPC, private subnet, PGA, Cloud NAT, no external IPs | Proposed |
| [0010](docs/adr/0010-data-quality-framework.md) | Reusable declarative DQ framework, quarantine + audit | Proposed |

---

## Change Log

- **2026-07-19** — Phase 1 authored: scaffold, architecture, data model, 10 ADRs,
  roadmap, standards, cost, risk. Awaiting review.
- **2026-07-19** — Review decisions applied: Silver format **Delta → Apache
  Iceberg** (ADR-0004); orchestration **local-only demo → real Cloud Composer**
  (ADR-0003, accepting ~$10–15/day, managed via destroy-between-breaks); teaching
  depth confirmed as full 15-step per phase.
- **2026-07-19** — **Phase 2 built:** `scb_common` library, five source
  generators, native-format CLI, local Docker stack, seed/bootstrap scripts.
  46 tests green; end-to-end generation verified. Awaiting review.
- **2026-07-20** — **Phase 3 built:** 6 Terraform modules + bootstrap +
  dev/uat/prod roots (private networking, least-privilege IAM, lifecycle buckets,
  secrets, $50 budget). `validate` Success on all roots; `fmt` clean. Not applied
  (needs user's GCP project). Reviewed & approved.
- **2026-07-20** — **Phase 4 built:** `bigquery` module + 20 tables (7 metadata,
  13 Gold) + `BigQueryMetadataStore`. `validate` Success on all roots; 52 tests
  green. Not applied. Reviewed & approved.
- **2026-07-20** — **Phase 5 built:** metadata-driven ingestion (`ingestion/` +
  5 source configs). Real run landed 4 file-based sources to Bronze (14 files),
  idempotency + audit + watermarks verified; 63 tests green. Reviewed & approved.
- **2026-07-20** — **Phase 6 built:** Spark/Iceberg Bronze→Silver transforms
  (DQ gate, dedup, SCD1/SCD2 MERGE) + silver_job + 2 configs. 76 tests green;
  DQ verified on real Bronze (31/1238 quarantined). Spark not executed (no JDK).
  Reviewed & approved.
- **2026-07-20** — **Phase 7 built:** Gold builders (dim_date, PIT SCD2 joins,
  fact assembly) + gold_job + config. 81 tests green; dim_date built for real
  (1,461 rows). Fact build needs JDK/Dataproc. Reviewed & approved.
- **2026-07-20** — **Phase 8 built:** guarded `composer` module + dynamic Airflow
  DAG (dag_builder pure/tested) + sensor plugin + local Airflow compose. 87 tests
  green; all Terraform roots validate. Composer stays OFF until deliberately enabled.
  Awaiting review.
