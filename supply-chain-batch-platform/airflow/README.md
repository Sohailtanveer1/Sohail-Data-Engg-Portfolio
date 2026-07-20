# airflow/

Airflow orchestration. **Implemented in Phase 8.**

| Path | Contents |
|---|---|
| `dags/dag_builder.py` | **pure** task-graph builder + acyclic guard (unit-tested) |
| `dags/supply_chain_daily.py` | dynamic daily DAG: sensors → ingest → Silver/Gold Dataproc batches; TaskGroups, pools, SLAs, XCom, trigger rules |
| `plugins/scb/sensors.py` | reschedule-mode `FileArrivalSensor` |
| `docker-compose.airflow.yml` | local Airflow ($0 DAG dev) |

Deploys to a real **Cloud Composer 2** env (guarded `composer` Terraform module,
`enable_composer=false` default, destroyed between breaks — ADR-0003). Cost
discipline + runbook: [docs/phase-08-orchestration.md](../docs/phase-08-orchestration.md).

```bash
docker compose -f airflow/docker-compose.airflow.yml up   # local, then http://localhost:8080
```
