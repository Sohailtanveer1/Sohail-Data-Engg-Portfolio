# Supply Chain Batch Data Platform on Google Cloud

A production-grade **batch** data engineering platform that consolidates data
from five enterprise supply-chain source systems into a governed, medallion
(Bronze → Silver → Gold) analytical platform on Google Cloud, served to
executives through BigQuery and Looker Studio.

This is the **batch** counterpart to the sibling
[`real-time-analytics-on-gcp`](../real-time-analytics-on-gcp) streaming
platform. Where that project answers *"what is happening right now?"*, this one
answers *"what happened, at scale, reliably, every day — and can I trust it?"*

> **Status: Phase 7 — Gold dimensional model built** (Phases 1–6 approved).
> Full medallion is coded: ingest → Bronze → Silver (Iceberg, DQ, SCD1/SCD2) →
> Gold star (point-in-time SK resolution) → BigQuery. **81 tests green**; DQ proven
> on real Bronze (31/1238 quarantined) and `dim_date` built for real (1,461 rows).
> GCP foundation + BigQuery (20 tables) are validated Terraform.
> _(Spark steps need a JDK/Dataproc — see docs/phase-06–07.)_ See
> [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) and [docs/](docs/) (`phase-02-*` … `phase-07-*`).

---

## Business Context

The company (a US supply-chain enterprise, QXO-style) operates **hundreds of
warehouses across North America**. Every day, five enterprise systems emit data
that must be consolidated into one trustworthy analytical platform to support
daily reporting, executive dashboards, and historical analysis.

| # | Source System | Technology | Format | Frequency | Provides |
|---|---|---|---|---|---|
| 1 | SAP ERP | SFTP | CSV | Daily | Purchase Orders, Material Master, Vendors, Goods Receipt, Inventory Valuation |
| 2 | Salesforce CRM | REST API | JSON | Hourly (incremental) | Customers, Accounts, Sales Reps, Credit Info |
| 3 | Warehouse Mgmt System (WMS) | PostgreSQL / JDBC | Table | Every 4 hours | Inventory, Locations, Stock Movement, Cycle Counts |
| 4 | Transportation Mgmt System (TMS) | Cloud Storage export | Parquet | Daily | Shipments, Carriers, Delivery Status, Routes, Freight Cost |
| 5 | Supplier Portal | SFTP | Excel (.xlsx) | Daily | Supplier Catalog, Price Lists, Lead Time, MOQ |

See [docs/source-systems.md](docs/source-systems.md) for the full analysis.

---

## Architecture (target)

```
Enterprise Systems (SAP, Salesforce, WMS, TMS, Supplier Portal)
        │  SFTP / REST / JDBC / GCS
        ▼
GCS Landing Bucket  ──►  Cloud Composer (Airflow orchestration)
                              │
                              ▼
                   Dataproc Serverless (PySpark ETL)
                              │
        ┌─────────────┬───────┴───────┬──────────────┐
        ▼             ▼               ▼              ▼
   Bronze (GCS)   Silver (GCS)     Gold (BigQuery)   Metadata/Audit (BigQuery)
   raw parquet    cleaned+SCD      star schema        control/audit/DQ/watermark
                              │
                              ▼
                       Looker Studio (executive dashboards)
```

Every resource is provisioned with **Terraform**, isolated across
`dev` / `uat` / `prod`, secured with least-privilege IAM and Secret Manager, and
observed via Cloud Logging + Cloud Monitoring. Full detail in
[docs/architecture/architecture-overview.md](docs/architecture/architecture-overview.md).

---

## Two modes: Enterprise vs Portfolio

Every design decision in this repo is documented in **two forms**:

- **Enterprise version** — how a Fortune 500 team builds it at scale.
- **Portfolio version** — how we implement the *same concepts* safely inside the
  **GCP Free Trial** (≈ $300 / 90 days), preferring local Docker execution and
  ephemeral/serverless GCP resources so nothing is left billing.

See [docs/cost-optimization.md](docs/cost-optimization.md) — read it before
provisioning anything.

---

## Repository Layout

| Path | Purpose | Populated in |
|---|---|---|
| `docs/` | Architecture, ADRs, data model, guides, cost/risk | Phase 1+ |
| `docs/adr/` | Architecture Decision Records | Phase 1+ |
| `infra/terraform/` | Reusable modules + per-env (`dev`/`uat`/`prod`) configs + bootstrap | Phase 3 |
| `data_generators/` | Local Python generators that emulate the 5 source systems | Phase 2 |
| `local/` | Docker Compose stack (Postgres WMS, mock Salesforce API, SFTP, local Airflow/Spark) | Phase 2 |
| `common/` | Shared Python package (config, logging, DQ, schema, metadata helpers) | Phase 2 |
| `ingestion/` | Land-to-Bronze extractors (SFTP, REST, JDBC, GCS) | Phase 5 |
| `spark/` | PySpark jobs (Bronze→Silver→Gold), transforms, tests | Phase 6–7 |
| `airflow/` | DAGs, task groups, sensors, plugins | Phase 8 |
| `bigquery/sql/` | Medallion + metadata/control/audit DDL & SQL | Phase 4 |
| `config/` | Metadata-driven pipeline configs (source & entity YAML) | Phase 5 |
| `tests/` | Unit / integration / end-to-end tests | Phase 6+ |
| `scripts/` | Operational scripts (bootstrap, backfill, cleanup) | Phase 2+ |
| `looker/` | Looker Studio dashboard definitions/notes | Phase 11 |
| `.github/workflows/` | CI/CD: format, lint, test, `terraform plan`, deploy | Phase 10 |

---

## Start here

1. [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) — where we are, phase by phase.
2. [docs/architecture/architecture-overview.md](docs/architecture/architecture-overview.md) — the system.
3. [docs/adr/](docs/adr/) — *why* every major decision was made.
4. [docs/roadmap.md](docs/roadmap.md) — the build plan and milestones.
5. [docs/cost-optimization.md](docs/cost-optimization.md) — how we stay inside the Free Trial.
