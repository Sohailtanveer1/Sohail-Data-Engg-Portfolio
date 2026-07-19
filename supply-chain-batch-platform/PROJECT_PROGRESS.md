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
| 1 | Planning & Architecture | 🟨 In review | Local (docs only) | $0 |
| 2 | Local dev environment + data generators + `common` package | ⬜ | Local (Docker) | $0 |
| 3 | Terraform foundation: APIs, VPC/networking, IAM, buckets, Secret Manager | ⬜ | GCP dev | ~$0–2 |
| 4 | BigQuery: datasets + metadata/control/audit + Gold DDL | ⬜ | GCP dev | ~$0 (free tier) |
| 5 | Ingestion: land 5 sources → Bronze (metadata-driven, file tracking, archive) | ⬜ | Local + GCP | ~$1–3 |
| 6 | Spark Bronze→Silver: schema validation, DQ, dedup, SCD1/SCD2, idempotency | ⬜ | Local Spark + Dataproc Serverless | ~$2–5 |
| 7 | Gold build: dimensional model → BigQuery | ⬜ | Dataproc Serverless + BQ | ~$1–3 |
| 8 | Orchestration: Airflow DAGs → **Cloud Composer** (managed) | ⬜ | Local dev + Cloud Composer | ⚠️ ~$10–15/day while up |
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

- [ ] **User reviews and approves the plan.** ← _we are here_
- [ ] Any requested changes to scope/decisions incorporated.

**Cleanup checklist (Phase 1):** none — no billable resources created.

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
