# Architecture Decision Records (ADRs)

Each ADR captures one significant decision: the context, the options considered,
the decision, and its consequences. They are the *"why"* behind the platform —
the material you defend in an interview.

Format: **Context → Options → Decision → Consequences → Enterprise vs Portfolio**.
Status values: Proposed · Accepted · Superseded.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-medallion-storage-layout.md) | Medallion storage layout: GCS lake + BigQuery serving | Proposed |
| [0002](0002-compute-dataproc-serverless.md) | Spark compute: Dataproc Serverless + local Spark | Proposed |
| [0003](0003-orchestration-airflow.md) | Orchestration: Cloud Composer (managed Airflow) | Proposed |
| [0004](0004-table-format-iceberg.md) | Silver table format: Apache Iceberg | Proposed |
| [0005](0005-metadata-driven-framework.md) | Metadata-driven pipeline framework | Proposed |
| [0006](0006-scd-strategy.md) | Slowly Changing Dimension strategy (SCD1/SCD2) | Proposed |
| [0007](0007-incremental-idempotency.md) | Incremental loading & idempotency | Proposed |
| [0008](0008-terraform-environments.md) | Terraform layout & environment isolation | Proposed |
| [0009](0009-networking.md) | Networking topology | Proposed |
| [0010](0010-data-quality-framework.md) | Data quality framework | Proposed |

New decisions get the next number and a row here.
