# airflow/dags/

DAG definitions: per-source daily/4-hourly pipelines with sensors, task groups,
retries, SLAs, branching, trigger rules. Generated from `config/`/control tables.
No transformation logic here — DAGs orchestrate only. **Phase 8.**
