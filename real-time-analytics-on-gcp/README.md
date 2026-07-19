# Real-Time Supply Chain Order & Inventory Analytics Platform

## Business Context

Warehouses across the supply chain network continuously emit **Order**,
**Inventory**, **Shipment**, **Return**, and **Supplier** events. Today these
events land in disconnected systems and are only visible to analysts hours
later via batch reports. That delay means stockouts, overselling, and
delayed shipments are discovered after they've already cost the business
money.

This platform ingests those events in real time, validates and enriches
them, and serves curated, trustworthy metrics to operations and finance
within seconds of an event occurring — not hours.

## Architecture

![Architecture diagram](images/image-2.png)

Supporting infrastructure (Terraform-managed, environment-isolated across
`dev` / `uat` / `prod`): VPC, firewall rules, IAM & service accounts, Secret
Manager, Cloud Storage, Cloud Logging/Monitoring.

## Repository Layout

| Path | Purpose |
|---|---|
| `kafka/` | Local Kafka producers, consumers, Docker Compose stack, Avro/JSON schemas |
| `dataflow/` | Apache Beam streaming pipeline (Pub/Sub → BigQuery) |
| `bigquery/` | Medallion schemas (bronze/silver/gold) and SQL |
| `infra/terraform/` | Reusable Terraform modules + per-environment configs |
| `docs/` | Architecture, diagrams, API docs, business docs, guides |
| `.github/workflows/` | CI/CD: lint, test, `terraform plan`, deploy |
| `tests/` | Unit, integration, and pipeline tests |
| `looker/` | Looker Studio dashboard definitions/notes |
| `scripts/` | Operational scripts (local bootstrap, replay, backfill) |

## 📖 Start here: [HANDBOOK.md](HANDBOOK.md)

**New to this project? Read [the Handbook](HANDBOOK.md) first.** It's the
single document that teaches the whole platform from zero, runs like a lab,
captures the real debugging journey, and arms you to defend every decision
in an interview. Everything else below is detail the Handbook links into.

## Project Status

✅ **Built and deployed end to end** — Kafka ingestion → Pub/Sub bridge →
Beam/Dataflow streaming pipeline → BigQuery Bronze/Silver/Gold → Looker
Studio, all running on live GCP (dev). Terraform-managed across
dev/uat/prod, least-privilege IAM, CI/CD, monitoring. 23 tests pass.

Known limitations are flagged openly (not hidden) in
[HANDBOOK.md §6.6](HANDBOOK.md#66--known-limitations-state-these-proactively--its-a-strength)
and [docs/lessons-learned.md](docs/lessons-learned.md).

## Getting Started

- **To learn / defend the project:** [HANDBOOK.md](HANDBOOK.md) — the front door.
- **To deploy it yourself, step by step:** [RUNBOOK.md](RUNBOOK.md) —
  exact commands, in order, with a verification checkpoint after each one.
- **To understand why it's built this way:** [docs/architecture/architecture-overview.md](docs/architecture/architecture-overview.md)
  (every data engineering concept explained with business value + interview framing).

## Documentation Index

| Doc | Covers |
|---|---|
| [RUNBOOK.md](RUNBOOK.md) | Step-by-step deployment to your own GCP project |
| [docs/setup-guide.md](docs/setup-guide.md) | High-level order of operations and prerequisites |
| [docs/architecture/architecture-overview.md](docs/architecture/architecture-overview.md) | Every DE concept (idempotency, dedup, watermarking, exactly-once, ...) with business value and interview framing |
| [docs/architecture/kafka-topic-design.md](docs/architecture/kafka-topic-design.md) | Topic naming, partition keys, replication rationale |
| [docs/diagrams/sequence/](docs/diagrams/sequence/) | Mermaid sequence diagrams: happy path, DLQ path, replay |
| [docs/diagrams/network/](docs/diagrams/network/) | Network topology and firewall reasoning |
| [docs/api/README.md](docs/api/README.md) | Event schema contracts + Gold view contracts |
| [docs/business/README.md](docs/business/README.md) | Business context, stakeholders, why real-time |
| [docs/security-guide.md](docs/security-guide.md) | Every IAM grant, explained |
| [docs/monitoring-guide.md](docs/monitoring-guide.md) | Alert-by-alert on-call runbook |
| [docs/troubleshooting-guide.md](docs/troubleshooting-guide.md) | DLQ triage, pipeline errors, local dev setup issues |
| [docs/testing-guide.md](docs/testing-guide.md) | What's tested, how to run it, what's intentionally not automated |
| [docs/cost-optimization.md](docs/cost-optimization.md) | Every cost lever, with reasoning |
| [docs/interview-questions.md](docs/interview-questions.md) | Curated Q&A across the whole platform |
| [docs/lessons-learned.md](docs/lessons-learned.md) | Real decisions, real problems hit, honest gaps |
| [infra/terraform/README.md](infra/terraform/README.md) | Terraform module layout and design rationale |
| [looker/dashboard-spec.md](looker/dashboard-spec.md) | Exact Looker Studio dashboard spec to build from |
