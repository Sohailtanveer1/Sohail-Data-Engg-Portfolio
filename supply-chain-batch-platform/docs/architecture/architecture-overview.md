# Architecture Overview

## 1. What we are building

A daily/near-daily **batch** platform that ingests five enterprise supply-chain
source systems, lands them in a governed data lake on Google Cloud, transforms
them through a **medallion architecture** (Bronze → Silver → Gold) using
**PySpark on Dataproc**, orchestrated by **Airflow (Cloud Composer)**, and serves
a **Kimball dimensional model** in **BigQuery** to **Looker Studio**.

The platform is **metadata-driven** (pipelines are configured, not hand-coded per
table), **idempotent** (safe to re-run), **observable** (structured logs, audit
tables, monitoring), and **secure** (least-privilege IAM, Secret Manager, private
networking). Everything is **Terraform-provisioned** and isolated across
`dev` / `uat` / `prod`.

---

## 2. End-to-end data flow

```
┌────────────────────────────────────────────────────────────────────────────┐
│  SOURCE SYSTEMS                                                             │
│  SAP ERP (SFTP/CSV)  Salesforce (REST/JSON)  WMS (Postgres/JDBC)           │
│  TMS (GCS/Parquet)   Supplier Portal (SFTP/Excel)                          │
└───────────────┬────────────────────────────────────────────────────────────┘
                │  extract (metadata-driven, per source connector)
                ▼
        ┌───────────────────┐   file & batch tracking, checksums, archive
        │  LANDING BUCKET   │   gs://scb-<proj>-<env>-landing/<source>/<date>/
        └─────────┬─────────┘
                  │  Composer triggers Dataproc Serverless batch
                  ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │  DATAPROC SERVERLESS  (PySpark)                                       │
   │                                                                       │
   │  BRONZE  raw, as-ingested → Parquet on GCS, partitioned by ingest_dt  │
   │     ▼   schema validation · type casting · dedup · DQ gate           │
   │  SILVER  cleaned/conformed → Iceberg on GCS, SCD1/SCD2, business keys │
   │     ▼   joins · aggregation · surrogate keys                         │
   │  GOLD    star schema (facts + dims) → loaded to BigQuery             │
   └───────────────────────────────┬─────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
     ┌────────────────┐   ┌───────────────────┐  ┌───────────────────┐
     │  BigQuery Gold │   │  BigQuery Metadata │  │  Cloud Logging /   │
     │  facts & dims  │   │  control · audit · │  │  Monitoring        │
     │                │   │  watermark · DQ    │  │  (alerts, metrics) │
     └───────┬────────┘   └───────────────────┘  └───────────────────┘
             ▼
     ┌────────────────┐
     │  Looker Studio │  executive & operational dashboards
     └────────────────┘
```

**Why the layers live where they do** (full rationale in
[ADR-0001](../adr/0001-medallion-storage-layout.md)):

- **Bronze & Silver on GCS** — Spark's native habitat. Cheap object storage,
  immutable raw history, columnar Parquet/Iceberg, full control over partitioning,
  SCD MERGE, and schema evolution. This is where the heavy transformation happens
  and where we *showcase Spark*.
- **Gold in BigQuery** — the serving layer. Serverless SQL, sub-second Looker
  queries, no cluster to keep warm, and a generous free tier (10 GB storage +
  1 TB query/month). This is where we *showcase BigQuery*.
- **Metadata/control/audit in BigQuery** — queryable operational state
  (watermarks, batch runs, DQ results) that pipelines and dashboards both read.

---

## 3. Component responsibilities

| Component | Responsibility | Enterprise | Portfolio (Free Trial) |
|---|---|---|---|
| **Landing bucket (GCS)** | First durable copy of every source file; immutable, archived | Multi-region, lifecycle to Coldline/Archive, retention lock | Single-region `us-central1`, lifecycle to Nearline after 30d |
| **Ingestion connectors** | Pull SFTP/REST/JDBC/GCS → land raw | Managed connectors (Fivetran/BigQuery DTS), airgapped SFTP | Python extractors + local Docker source emulators |
| **Cloud Composer / Airflow** | Orchestrate, schedule, sense, retry, SLA | Multiple HA Composer envs, autoscaling | **Real Composer 2 env** (Phase 8+); local Airflow for dev; destroy between breaks |
| **Dataproc (Spark)** | Bronze→Silver→Gold transforms | Autoscaling clusters or ephemeral job clusters | **Dataproc Serverless** batches + **local Spark** for dev |
| **BigQuery** | Serve Gold + hold metadata/audit | Slots/reservations, multi-region, column policies | On-demand pricing, single dataset per env, free tier |
| **Secret Manager** | SFTP creds, SF token, Postgres password | Rotation, CMEK | Manual secrets, no rotation |
| **IAM / Service Accounts** | Least-privilege identity per component | Workload Identity Fed, org policies | Per-component SAs, minimal roles |
| **VPC / NAT / firewall** | Private, egress-controlled networking | Shared VPC, PSC, Cloud Armor | Custom VPC, private subnet, PGA, Cloud NAT |
| **Cloud Logging / Monitoring** | Observability, alerts, dashboards | SLO-based alerting, log sinks to BQ | Log-based metrics + a few alert policies |
| **Looker Studio** | Dashboards | Looker (governed) | Looker Studio (free) on BigQuery |

---

## 4. Medallion contract (what each layer guarantees)

- **Bronze** — *"exactly what the source sent, plus lineage."* No business logic.
  Raw types preserved (mostly string), append-only, partitioned by `ingest_date`
  and `source_system`. Audit columns added: `batch_id`, `source_file`,
  `ingest_ts`, `row_hash`. Enables full replay.
- **Silver** — *"clean, conformed, trustworthy, deduplicated, current + history."*
  Typed columns, standardized units/currencies, validated against DQ rules,
  business keys enforced, SCD1/SCD2 applied. This is the enterprise "single source
  of truth" that many consumers could query directly.
- **Gold** — *"business-ready answers."* Dimensional star schema (facts + dims),
  pre-joined and aggregated for specific analytical questions (inventory health,
  supplier performance, freight cost, order fulfillment). Optimized for Looker.

See [data-model.md](data-model.md) for the full schema.

---

## 5. Cross-cutting frameworks (built once, reused everywhere)

1. **Metadata-driven pipeline framework** — a table (source/entity config in YAML
   + control tables in BigQuery) drives *which* entities load, *how* (full vs
   incremental), *what* schema and DQ rules apply, and *where* they land. Adding a
   new table = adding a config row, not a new pipeline. ([ADR-0005](../adr/0005-metadata-driven-framework.md))
2. **Schema validation & evolution** — every dataframe is validated against a
   registered contract before promotion; additive changes auto-evolve, breaking
   changes fail loudly. ([ADR-0004](../adr/0004-table-format-iceberg.md))
3. **Data quality framework** — declarative rules (not-null, uniqueness, ranges,
   referential, freshness) evaluated per batch; failures quarantined and audited.
   ([ADR-0010](../adr/0010-data-quality-framework.md))
4. **Idempotency & incremental** — watermark-based incremental extraction +
   idempotent writes (Iceberg MERGE INTO / partition overwrite) so any re-run converges
   to the same state. ([ADR-0007](../adr/0007-incremental-idempotency.md))
5. **Observability** — structured JSON logging with a common envelope
   (`pipeline`, `batch_id`, `source`, `rows_read/written/rejected`, `duration`,
   `status`) + audit/control tables + Cloud Monitoring alerts.

---

## 6. Terraform module plan

Reusable modules under `infra/terraform/modules/`, composed per environment under
`infra/terraform/environments/{dev,uat,prod}/`. Detail in
[ADR-0008](../adr/0008-terraform-environments.md).

| Module | Creates | Key inputs | Notes |
|---|---|---|---|
| `project_services` | Enables required GCP APIs | `project_id`, `services[]` | First to apply |
| `networking` | VPC, private subnet, Cloud Router, Cloud NAT, firewall, PGA | `region`, CIDR ranges | No external IPs ([ADR-0009](../adr/0009-networking.md)) |
| `iam` | Service accounts + least-privilege role bindings | SA list, role map | One SA per component |
| `secret_manager` | Secrets + accessor bindings | secret names | Values injected out-of-band |
| `storage` | Buckets: landing, bronze, silver, gold, archive, temp, dataproc-staging, tf-state | lifecycle rules | Uniform bucket-level access |
| `bigquery` | Datasets (gold, metadata) + tables/views | dataset ids, schemas | Free-tier aware |
| `dataproc` | Serverless batch config / (optional) cluster template, staging bucket, subnet binding | machine config | Serverless default |
| `composer` | Composer 2 environment | node config, env vars | `enable_composer` flag; default OFF, set ON in Phase 8 |
| `monitoring` | Log-based metrics, alert policies, notification channel | thresholds | Email channel |

`bootstrap/` provisions the remote-state bucket and the CI deployer SA (the
chicken-and-egg layer that must exist before the main stack).

---

## 7. Environments

`dev` (default working env) → `uat` (integration/promotion) → `prod` (final).
Same modules, different `*.tfvars` (project, region, sizing, flags). Remote state
in a versioned GCS bucket, one state prefix per env. Promotion is git + CI driven,
not manual clicking. ([ADR-0008](../adr/0008-terraform-environments.md))

---

## 8. What runs where (cost posture)

| Stage | Local (Docker/laptop) | GCP |
|---|---|---|
| Source emulation | ✅ Python generators, Postgres, mock REST API, SFTP | — |
| Development & unit tests | ✅ local Spark, local Airflow | — |
| Bronze/Silver/Gold at "real" scale | — | ✅ Dataproc Serverless |
| Serving & dashboards | — | ✅ BigQuery + Looker Studio |
| Orchestration | ✅ local Airflow (dev/iteration) | ⚠️ Cloud Composer (Phase 8+, destroy between breaks) |

Guiding principle: **prefer local execution; use GCP for the services we want to
demonstrate; keep compute serverless/ephemeral, and actively tear down the one
always-on exception (Cloud Composer) between work sessions.** See
[cost-optimization.md](../cost-optimization.md).
