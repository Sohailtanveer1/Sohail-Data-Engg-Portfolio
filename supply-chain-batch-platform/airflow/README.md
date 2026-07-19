# airflow/

Airflow orchestration. `dags/` = DAGs (dynamically generated from metadata),
`plugins/` = custom operators/sensors/hooks. Environment-portable: runs on local
Airflow (dev iteration) and a real **Cloud Composer 2** environment (Phase 8+,
destroyed between breaks — ADR-0003). **Populated in Phase 8.**
