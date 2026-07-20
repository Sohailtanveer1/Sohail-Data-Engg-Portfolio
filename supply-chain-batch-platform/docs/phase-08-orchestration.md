# Phase 8 — Orchestration: Airflow DAGs → Cloud Composer

> The 15-step walkthrough for wiring the whole daily batch (ingest → Silver →
> Gold) into Airflow, developed locally then deployed to a **real Cloud Composer**
> environment (ADR-0003). Composer is guarded and cost-managed.

> **Execution note:** Airflow doesn't run on this box's Python 3.14. The DAG
> *shape* is built by a pure, unit-tested `dag_builder`; the DAG/plugin files are
> compile-checked; the Composer Terraform validates. Run locally via the provided
> Airflow compose (Docker) or on Composer.

---

## 1. Objectives

Orchestrate the full daily pipeline with sensors, retries, SLAs, pools, and
trigger rules — **generated dynamically from metadata** — and deploy it to a
managed Cloud Composer environment (cost-controlled).

## 2. Theory

- **Dynamic DAGs from metadata**: the task graph is derived from the same
  source/silver/gold config, so adding an entity changes the DAG without editing it.
- **Idempotent tasks**: every task (ingest checksum-dedup, Silver/Gold MERGE) is
  safe to retry — the foundation for Airflow retries to be *correct*, not just automatic.
- **Sensors in `reschedule` mode** free the worker slot while waiting — essential
  on a small Composer env.
- **Pools** cap concurrent Dataproc batches; **SLAs** alert on lateness;
  **trigger rules** (`all_done` on `end`) make the run finalize even on partial failure.

## 3. Business Context

The daily batch must be reliable and observable: land only when the source's drop
is complete (sensor), retry transient cloud hiccups, alert if it breaches the
3-hour SLA, and never double-process. Composer gives operations the familiar
Airflow UI, logs, and history a real team runs on.

## 4. Architecture

```
                 ┌───────── TaskGroup: sap_erp ─────────┐
start ─┬─► wait_sap_erp ─► ingest_sap_erp ─► silver_material_master ─┐
       │         (sensor,       (Python)        (Dataproc batch)     │
       │          reschedule)                                        ├─► gold_fact_purchase_order ─► end
       ├─► ingest_wms (JDBC, no sensor) ─► silver_inventory ─────────┘        (Dataproc batch)     (all_done)
       └─► dim_date (Python → BigQuery) ─────────────────────────────────────────────────────────►┘
```

## 5. Folder Creation

[`airflow/dags/`](../airflow/dags) (`dag_builder.py`, `supply_chain_daily.py`),
[`airflow/plugins/scb/`](../airflow/plugins/scb) (`sensors.py`),
[`airflow/tests/`](../airflow/tests), and `airflow/docker-compose.airflow.yml`.

## 6. Infrastructure

- **`composer` Terraform module** — guarded (`enable=false` default), Composer 2,
  smallest workloads, private subnet, `composer` SA, the `composer-pods/services`
  secondary ranges. Wired into all env roots behind `enable_composer`.
- **Local Airflow** — a one-container `standalone` compose mounts `dags/`,
  `plugins/`, and the repo so everything imports; for $0 DAG development.

## 7. Implementation

| Piece | Kind |
|---|---|
| `dag_builder.build_pipeline` | **pure** — spec of tasks + dependencies from config (tested) |
| `validate_acyclic` | **pure** — cycle/dangling-edge guard (tested) |
| `supply_chain_daily.py` | Airflow — maps spec → operators, TaskGroups, pools, SLAs |
| `scb/sensors.FileArrivalSensor` | Airflow — reschedule-mode source-readiness sensor |
| Silver/Gold tasks | `DataprocCreateBatchOperator` (Serverless), pooled |

## 8. Testing / Verification

- **87 tests passing** (+6 DAG-builder: expected tasks, JDBC-has-no-sensor,
  dependency wiring, acyclic check, dangling/cycle detection).
- Airflow DAG/plugin modules **compile**; the pure builder is fully tested.
- Composer module **`terraform validate` Success** on dev/uat/prod; `fmt` clean.

## 9. Documentation

This doc + `airflow/` READMEs + PROJECT_PROGRESS.

## 10. Code Review notes

- `end` uses `TriggerRule.ALL_DONE` so the run finalizes/audits even if a branch
  failed (partial-failure visibility), while inner tasks use `ALL_SUCCESS`.
- Sensors use `mode="reschedule"` (not `poke`) to avoid holding a worker slot.
- The DAG imports repo packages (`ingestion`, `scb_common`, Spark jobs) — the
  compose/Composer `PYTHONPATH` and `pypi_packages` must include them.

## 11. Airflow topics (the requested coverage)

| Topic | Where |
|---|---|
| DAG design | `supply_chain_daily.py` (schedule, catchup=False, max_active_runs=1) |
| Dynamic DAGs | `dag_builder.build_pipeline` generates tasks from config |
| Task groups | one `TaskGroup` per source |
| Sensors | `FileArrivalSensor` (reschedule) gate ingest |
| Branching | JDBC vs file-based path (sensor only for file sources) |
| Retries | `default_args.retries=2`, exponential-ish `retry_delay` |
| SLAs | `default_args.sla=3h` |
| Variables | env vars (`SCB_*`) → Composer `env_variables` |
| Connections | Dataproc/BigQuery via the Composer service account (Workload Identity) |
| Pools | `dataproc_pool` caps concurrent Serverless batches |
| XCom | `_run_ingest` returns `{source, date}` for downstream |
| Trigger rules | `end` = `all_done`; inner = `all_success` |
| Error handling | typed task failures + audit rows + SLA/retry |

## 12. Best Practices applied

Config-driven DAGs; idempotent tasks; reschedule sensors; pools for cost/concurrency;
SLAs; local-dev parity with Composer; least-privilege Composer SA; guarded, tearable
infra.

## 13. Common Mistakes (avoided)

Hand-maintaining a giant static DAG; poke-mode sensors hogging slots; retries on
non-idempotent tasks (double counts); leaving Composer running (cost); putting
transformation logic in the DAG (DAGs orchestrate, jobs transform).

## 14. Cost Considerations

- **Local Airflow: $0.** Develop and parse DAGs here.
- **Cloud Composer: the project's biggest cost** (~$10–15/day, no scale-to-zero).
  Guarded by `enable_composer=false`; created deliberately in Phase 8 and
  **`terraform destroy`-ed between multi-day breaks**. $50 budget alert backstop.
- Dataproc batches triggered by the DAG are Serverless (pay-per-run, auto-terminate).

## 15. Next Steps

**Phase 9 — Data quality, monitoring & logging:** harden the DQ framework, add
Cloud Logging structured sinks, log-based metrics, alert policies (pipeline
failure, freshness, runtime), and an audit/monitoring view — the `monitoring`
Terraform module.

---

## Runbook — Composer (cost-managed)

```bash
cd infra/terraform/environments/dev
# turn Composer ON deliberately
terraform apply -var-file=dev.tfvars -var="enable_composer=true"     # ~25-40 min to build
terraform output composer_dag_prefix     # gs://.../dags

# deploy DAGs + plugins + repo deps
gsutil -m rsync -r airflow/dags   <dag_prefix>
gsutil -m rsync -r airflow/plugins <dag_prefix>/../plugins
# open the UI
terraform output composer_airflow_uri

# ⚠️ when done for the day/week — DESTROY Composer to stop the meter
terraform apply -var-file=dev.tfvars -var="enable_composer=false"
# (or destroy just the module target); DAGs live in git and redeploy in minutes.
```

## Run locally ($0)

```bash
docker compose -f airflow/docker-compose.airflow.yml up
# http://localhost:8080  → trigger `supply_chain_daily`
```
