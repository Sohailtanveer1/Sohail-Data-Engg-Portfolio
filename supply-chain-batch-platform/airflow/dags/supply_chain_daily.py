"""Daily supply-chain batch DAG (metadata-driven).

Shape comes from `dag_builder.build_pipeline` (unit-tested); this file turns the
spec into operators and wires:
  sensors (reschedule) → ingest (PythonOperator) → silver/gold (Dataproc
  Serverless batches, pooled) with dim_date in parallel.

Demonstrates: dynamic DAG generation, TaskGroups, sensors, retries, SLAs, pools,
XCom, and trigger rules. Runs on local Airflow (dev) and Cloud Composer (Phase 8).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule

from dag_builder import build_pipeline, validate_acyclic

# --- platform config (env-overridable; set as Composer env vars) --------------
PROJECT = os.environ.get("SCB_PROJECT", "scb-platform-dev")
REGION = os.environ.get("SCB_REGION", "us-central1")
GOLD_DATASET = os.environ.get("SCB_GOLD_DATASET", "scb_gold_dev")
GCS = os.environ.get("SCB_ARTIFACTS", "gs://scb-scb-platform-dev-dev-artifacts")
STAGING = os.environ.get("SCB_STAGING", "scb-scb-platform-dev-dev-dataproc-staging")
TEMP_BUCKET = os.environ.get("SCB_TEMP", "scb-scb-platform-dev-dev-temp")
DP_SA = os.environ.get("SCB_DATAPROC_SA", f"scb-dev-dataproc@{PROJECT}.iam.gserviceaccount.com")
SUBNET = os.environ.get("SCB_SUBNET",
                        f"projects/{PROJECT}/regions/{REGION}/subnetworks/scb-dev-subnet-{REGION}")
ICEBERG_JAR = f"{GCS}/jars/iceberg-spark-runtime-3.5_2.12-1.6.1.jar"
BQ_JAR = f"{GCS}/jars/spark-bigquery-with-dependencies.jar"

# --- platform metadata (mirrors config/) --------------------------------------
SOURCES = ["sap_erp", "salesforce", "wms", "tms", "supplier_portal"]
FILE_BASED = {"sap_erp", "salesforce", "tms", "supplier_portal"}  # wms is JDBC
SILVER_ENTITIES = {"material_master": "sap_erp", "purchase_order": "sap_erp"}
GOLD_ENTITIES = {"fact_purchase_order": ["material_master", "purchase_order"]}

SPEC = build_pipeline(SOURCES, SILVER_ENTITIES, GOLD_ENTITIES, FILE_BASED)
validate_acyclic(SPEC)

default_args = {
    "owner": "data-eng",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "sla": timedelta(hours=3),
    "depends_on_past": False,
}


def _run_ingest(source: str, **context):
    """Land a source to Bronze; push the batch id to XCom."""
    from ingestion.run import main as ingest_main
    ds = context["ds"]
    ingest_main(["--source", source, "--date", ds])
    return {"source": source, "date": ds}


def _run_dim_date(**context):
    from scripts.build_dim_date import main as dim_main
    dim_main(["--start", "2024-01-01", "--end", "2027-12-31",
              "--bq-project", PROJECT, "--bq-dataset", GOLD_DATASET])


def _spark_batch(main_file: str, args: list[str], jars: list[str]) -> dict:
    return {
        "pyspark_batch": {
            "main_python_file_uri": f"{GCS}/{main_file}",
            "args": args,
            "jar_file_uris": jars,
        },
        "runtime_config": {"version": "2.2"},
        "environment_config": {
            "execution_config": {"service_account": DP_SA, "subnetwork_uri": SUBNET,
                                 "staging_bucket": STAGING},
        },
    }


def _make_operator(spec, dag, groups):
    from airflow.providers.google.cloud.operators.dataproc import DataprocCreateBatchOperator

    from scb.sensors import FileArrivalSensor

    tg = groups.get(spec.group)
    common = {"task_id": spec.task_id, "task_group": tg, "dag": dag}

    if spec.kind == "marker":
        return EmptyOperator(trigger_rule=TriggerRule.ALL_DONE if spec.task_id == "end"
                             else TriggerRule.ALL_SUCCESS, **common)
    if spec.kind == "sensor":
        return FileArrivalSensor(
            path=f"/home/airflow/gcs/data/landing/{spec.params['source']}/{{{{ ds }}}}/_SUCCESS",
            mode="reschedule", poke_interval=300, timeout=60 * 60 * 2, **common)
    if spec.kind == "ingest":
        return PythonOperator(python_callable=_run_ingest,
                              op_kwargs={"source": spec.params["source"]}, **common)
    if spec.params.get("entity") == "dim_date":
        return PythonOperator(python_callable=_run_dim_date, **common)
    if spec.kind == "silver":
        return DataprocCreateBatchOperator(
            region=REGION, project_id=PROJECT, pool="dataproc_pool",
            batch=_spark_batch("spark/jobs/silver_job.py",
                               ["--entity", spec.params["entity"]], [ICEBERG_JAR]),
            batch_id=f"scb-silver-{spec.params['entity']}-{{{{ ds_nodash }}}}", **common)
    if spec.kind == "gold":
        return DataprocCreateBatchOperator(
            region=REGION, project_id=PROJECT, pool="dataproc_pool",
            batch=_spark_batch("spark/jobs/gold_job.py",
                               ["--entity", spec.params["entity"], "--project", PROJECT,
                                "--dataset", GOLD_DATASET, "--temp-bucket", TEMP_BUCKET],
                               [ICEBERG_JAR, BQ_JAR]),
            batch_id=f"scb-gold-{spec.params['entity']}-{{{{ ds_nodash }}}}", **common)
    raise ValueError(f"Unknown task kind: {spec.kind}")


with DAG(
    dag_id="supply_chain_daily",
    description="Daily batch: ingest -> Silver -> Gold -> BigQuery",
    schedule="0 6 * * *",          # 06:00 UTC daily
    start_date=datetime(2026, 7, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["supply-chain", "batch", "medallion"],
) as dag:
    group_names = {s.group for s in SPEC if s.group}
    groups = {name: TaskGroup(group_id=name, dag=dag) for name in group_names}

    tasks = {s.task_id: _make_operator(s, dag, groups) for s in SPEC}
    for s in SPEC:
        for up in s.upstream:
            tasks[up] >> tasks[s.task_id]
