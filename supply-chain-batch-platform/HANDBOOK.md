# HANDBOOK — Supply Chain Batch Data Platform

**The single front door.** Read this to understand the whole platform from zero,
to run it, and to defend every decision in an interview. Everything else is detail
this links into.

---

## 1. What it is, in one paragraph

A production-grade **batch** data platform on Google Cloud that consolidates five
enterprise supply-chain sources (SAP ERP, Salesforce, a WMS, a TMS, a Supplier
Portal) into a governed **medallion** lake (Bronze → Silver → Gold) and serves a
**Kimball star schema** in BigQuery to Looker Studio. It is **metadata-driven**,
**idempotent**, **observable**, **secure**, and **entirely Terraform-provisioned**
across `dev`/`uat`/`prod` — built to run inside the GCP Free Trial by preferring
local execution and serverless/ephemeral compute.

## 2. The 30-second architecture

```
5 sources → GCS landing → (Airflow/Composer) → Dataproc Serverless (PySpark)
   → Bronze (raw Parquet) → Silver (Iceberg: typed, DQ-gated, SCD1/SCD2)
   → Gold (star schema → BigQuery) → Looker Studio
   with metadata/control/audit + monitoring throughout
```

Full detail: [docs/architecture/architecture-overview.md](docs/architecture/architecture-overview.md).

## 3. How it was built — the 11 phases

Each phase is a self-contained lesson with a walkthrough doc. See
[PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) for status.

| # | Phase | Doc | Headline artifact |
|---|---|---|---|
| 1 | Planning & architecture | [ADRs](docs/adr/) | 10 ADRs, data model, roadmap |
| 2 | Local dev environment | [phase-02](docs/phase-02-local-environment.md) | `scb_common` + 5 generators + Docker stack |
| 3 | Terraform foundation | [phase-03](docs/phase-03-terraform-foundation.md) | 6 modules, networking, IAM, buckets, budget |
| 4 | BigQuery + metadata | [phase-04](docs/phase-04-bigquery-metadata.md) | 20 tables, BigQuery store |
| 5 | Ingestion → Bronze | [phase-05](docs/phase-05-ingestion.md) | metadata-driven extractors, idempotency |
| 6 | Spark → Silver | [phase-06](docs/phase-06-spark-silver.md) | Iceberg, DQ gate, SCD1/SCD2 MERGE |
| 7 | Gold → BigQuery | [phase-07](docs/phase-07-gold.md) | PIT joins, dim_date, star schema |
| 8 | Orchestration | [phase-08](docs/phase-08-orchestration.md) | dynamic DAG, guarded Composer |
| 9 | DQ, monitoring, logging | [phase-09](docs/phase-09-monitoring.md) | log metrics, alerts, freshness |
| 10 | CI/CD | [phase-10](docs/phase-10-cicd.md) | GitHub Actions gate, WIF deploy |
| 11 | Serve & hand off | [phase-11](docs/phase-11-delivery.md) | Looker, DR, runbook, this handbook |

## 4. Run it

- **Locally ($0):** [RUNBOOK.md §Local](RUNBOOK.md#a-local-everything-0). Generate
  data → land to Bronze → (DQ verified) → freshness monitor. Spark/Airflow need a
  JDK/Docker.
- **On GCP:** [RUNBOOK.md §Cloud](RUNBOOK.md#b-gcp-dev). `terraform apply` the
  foundation + BigQuery, run Silver/Gold on Dataproc Serverless, optionally Composer.
- **Tear it all down:** [RUNBOOK.md §Cleanup](RUNBOOK.md#c-cleanup--verify-0-run-rate).

## 5. The decisions you must be able to defend (ADRs)

| Decision | Why | ADR |
|---|---|---|
| GCS lake + BigQuery serving | showcase Spark *and* BigQuery, cheaply | [0001](docs/adr/0001-medallion-storage-layout.md) |
| Dataproc **Serverless** (no cluster) | zero idle cost — the top cost risk removed | [0002](docs/adr/0002-compute-dataproc-serverless.md) |
| Real Cloud Composer, guarded | genuine managed Airflow, destroyed between breaks | [0003](docs/adr/0003-orchestration-airflow.md) |
| **Iceberg** for Silver | ACID MERGE + BigQuery-readable + evolution | [0004](docs/adr/0004-table-format-iceberg.md) |
| Metadata-driven pipelines | onboard a table with config, not code | [0005](docs/adr/0005-metadata-driven-framework.md) |
| SCD2 where history matters | point-in-time correctness of facts | [0006](docs/adr/0006-scd-strategy.md) |
| Watermark + idempotent MERGE | safe, efficient re-runs | [0007](docs/adr/0007-incremental-idempotency.md) |
| Per-env Terraform roots | isolation, clean apply/destroy | [0008](docs/adr/0008-terraform-environments.md) |
| Private VPC, no public IPs | defensible security posture | [0009](docs/adr/0009-networking.md) |
| Declarative DQ framework | consistent quarantine + audit | [0010](docs/adr/0010-data-quality-framework.md) |

## 6. The engineering ideas that make it "senior"

1. **One rule set, two engines** — DQ/schema rules are data; evaluated in pure
   Python (fast tests) *and* Spark (scale). No drift.
2. **`batch_id` as the spine** — one correlation key ties logs, audit tables, DQ
   results, and output partitions together.
3. **Idempotency everywhere** — checksum file-dedup, watermarks, MERGE/partition
   overwrite; any re-run converges. This is what makes Airflow retries *correct*.
4. **Bronze = raw strings (schema-on-read)** — robust to source mess; typing is
   Silver's job under a DQ gate.
5. **Point-in-time SCD2 joins** — facts reflect dimension attributes *as of* the
   event, not today.
6. **Freshness = absence of success** — the alert that catches a silent scheduler
   death, not just a task failure.
7. **Cost as a first-class design constraint** — serverless/ephemeral compute,
   guarded Composer, `terraform destroy`-ability, a $50 budget alert.

## 7. Honest limitations (state these — it's a strength)

- **Spark & Airflow weren't executed on the authoring machine** (no JDK; Python
  3.14). Their *logic* is pure-unit-tested, jobs/DAGs compile-checked, and run on a
  local JDK/Docker or Dataproc/Composer via the runbook.
- **Terraform wasn't `apply`-ed** here (needs a real project) — it `validate`s and
  `fmt`s clean across all four roots; the runbook applies it.
- Silver/Gold ship **representative entities** (e.g. `material_master`,
  `purchase_order`, `fact_purchase_order`); the framework generalizes to the rest
  by adding config, not code.
- Excel/JDBC connectors read the same payloads their live counterparts serve; a
  live-HTTP Salesforce connector is a documented extension.

More: [docs/lessons-learned.md](docs/lessons-learned.md).

## 8. Where to go next

- Defend decisions → [docs/interview-questions.md](docs/interview-questions.md)
- Deploy → [RUNBOOK.md](RUNBOOK.md)
- When it breaks → [docs/troubleshooting-guide.md](docs/troubleshooting-guide.md)
- If disaster strikes → [docs/disaster-recovery.md](docs/disaster-recovery.md)
- Security posture → [docs/security-guide.md](docs/security-guide.md)
- Contribute → [CONTRIBUTING.md](CONTRIBUTING.md)
