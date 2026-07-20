# Interview Questions

The questions this project prepares you to answer, grouped by topic, with the
one-line answer and where it's implemented. Defend, don't recite.

---

## Architecture

- **Why medallion (Bronze/Silver/Gold)?** Separation of concerns: immutable raw
  (replay), clean conformed truth (governed), business-ready marts (fast serving).
- **Why GCS lake + BigQuery serving, not all-BigQuery?** Showcase heavy Spark
  transformation where it's strongest and serverless SQL serving where it's
  strongest; cheap; Iceberg keeps Silver BigQuery-readable. (ADR-0001)
- **Why Iceberg over Delta/Parquet for Silver?** ACID `MERGE` for SCD, schema +
  partition evolution, time-travel, and multi-engine (BigQuery can read it). (ADR-0004)

## Ingestion & idempotency

- **How do you avoid double-processing?** SHA-256 **file checksums** in
  `file_audit` skip already-seen files; watermarks bound incremental reads. (ADR-0007)
- **What makes a re-run safe?** Idempotent writes — Iceberg `MERGE` for dims,
  dynamic partition overwrite for facts — so any re-run converges.
- **Full vs incremental — how decided?** Per entity in config: master data =
  full → SCD; transactions = incremental by watermark column.
- **Why store Bronze as strings?** Schema-on-read: raw fidelity + robustness to
  mixed/dirty columns; typing happens in Silver under a DQ gate.

## Modeling (Kimball)

- **Surrogate vs business keys?** SK versions a dimension row independently of the
  BK, which is what makes SCD2 history joinable from facts.
- **SCD1 vs SCD2 — when?** SCD2 where point-in-time history matters (material cost,
  credit limit); SCD1 where corrections just overwrite (carrier name). (ADR-0006)
- **What's a point-in-time join?** Join an SCD2 dim on BK **and** `fact_date ∈
  [effective_from, effective_to)` — attribute values *as of* the event.
- **Semi-additive measures?** Inventory on-hand: sum across warehouses, never
  across days. Flagged in the schema.
- **Late-arriving dimension?** LEFT JOIN keeps the fact (SK null), backfilled later.

## Spark

- **Partitioning vs bucketing vs clustering?** Partition prunes files by a column;
  clustering (BigQuery) sorts within partitions; bucketing pre-shuffles joins.
- **How do you handle skew / small files / big joins?** AQE skew-join + coalesce;
  broadcast small dims (`autoBroadcastJoinThreshold`); Iceberg compaction.
- **Why never `inferSchema` in prod?** Non-deterministic, slow, hides drift —
  we use explicit `TableSchema` contracts.

## BigQuery

- **Partition + cluster — why?** They directly reduce **bytes billed**, which is
  BigQuery's cost model; facts partition by event date, cluster by material/warehouse.
- **Money type?** `NUMERIC` (exact decimal), never FLOAT.

## Orchestration (Airflow)

- **Dynamic DAGs?** The task graph is generated from metadata (`dag_builder`), so
  a new entity is config, not DAG edits.
- **Sensor mode?** `reschedule` frees the worker slot while waiting — critical on
  a small Composer env.
- **Trigger rules?** `end` uses `all_done` so the run finalizes/audits even on
  partial failure; inner tasks use `all_success`.
- **Why are retries safe?** Because every task is idempotent.

## Security & IAM

- **Least privilege across layers?** One SA per component; project/bucket/secret
  roles granted only where needed; cross-SA `actAs` explicit.
- **Secrets?** Secret Manager; values never in Terraform state; `secretAccessor`
  scoped to the ingestion SA.
- **CI auth?** Workload Identity Federation (keyless OIDC), scoped deployer SA.
- **Network?** Private subnet, no public IPs, PGA + NAT, deny-by-default firewall.

## Reliability & observability

- **How do you know last night's batch ran?** Freshness = **absence of a success**
  metric within the window (+ the audit-trail freshness monitor).
- **DQ failure vs corrupted file?** Breached DQ threshold **fails** the batch; a
  corrupted file is **quarantined** and the batch continues.
- **What's `batch_id`?** The correlation key tying logs, audit, DQ, and outputs.

## Terraform & CI/CD

- **Environment isolation?** Per-env roots composing shared modules, one state
  prefix each; promotion is plan-on-PR / apply-on-merge. (ADR-0008)
- **Guarding cost?** Composer behind `enable_composer=false`; Dataproc Serverless
  (no idle cluster); $50 budget alert; `terraform destroy`-ability.

## Cost (Free Trial)

- **Biggest risk and mitigation?** Cloud Composer (~$10–15/day, no scale-to-zero)
  — guarded off, created deliberately, destroyed between breaks.
- **How is compute kept cheap?** Serverless/ephemeral only; local dev for
  iteration; nothing always-on except tiny buckets/network.
