"""Bronze -> Silver Spark job (config-driven, Iceberg).

Pipeline per entity (config in config/silver/<entity>.yaml):
    read Bronze parquet -> cast to Silver types -> dedup on business key
    -> DQ gate (quarantine failures) -> add row_hash/effective-dating/surrogate
    -> Iceberg MERGE (SCD2 for history dims, SCD1/upsert for the rest)
    -> write quarantine + dq_results + batch_audit.

Runs on local Spark (JDK + pyspark) or Dataproc Serverless — same code. The pure
builders it calls are unit-tested (spark/tests); this orchestration is
compile-checked and executed on a real Spark runtime (see docs/phase-06).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scb_common.context import BatchContext
from scb_common.dq import DQReport, rule_from_dict
from scb_common.logging import get_logger
from scb_common.metadata import (
    BatchAudit,
    DQResultRecord,
    JsonlMetadataStore,
    finalize,
)
from scb_common.schema import TableSchema
from spark.transforms.clean import add_row_hash, add_surrogate_key, apply_casts, apply_dedup
from spark.transforms.dq_spark import evaluate_spark
from spark.transforms.expressions import SPARK_TYPES, build_create_iceberg_table
from spark.transforms.scd import apply_scd1, apply_scd2

SCD_COLUMNS = [
    ("effective_from", "timestamp"),
    ("effective_to", "timestamp"),
    ("is_current", "boolean"),
    ("row_hash", "string"),
    ("batch_id", "string"),
]


def _ensure_scd2_table(
    spark, table: str, sk: str, business_keys: list[str], tracked: list[str], schema: TableSchema
) -> list[str]:
    col_types = {c.name: SPARK_TYPES[c.dtype] for c in schema.columns}
    cols = (
        [(sk, "string")]
        + [(k, col_types[k]) for k in business_keys]
        + [(t, col_types[t]) for t in tracked]
        + SCD_COLUMNS
    )
    spark.sql(build_create_iceberg_table(table, cols))
    return [c for c, _ in cols]


def run_silver(
    spark,
    entity_cfg: dict,
    *,
    bronze_root: str,
    catalog: str,
    metastore,
    quarantine_root: str,
    env: str = "local",
) -> None:
    entity = entity_cfg["entity"]
    source = entity_cfg["source"]
    scd = entity_cfg.get("scd", "upsert")
    business_keys = entity_cfg["business_keys"]
    tracked = entity_cfg.get("tracked_columns", [])
    target = entity_cfg["target_table"].replace("scb.", f"{catalog}.")

    ctx = BatchContext(
        pipeline=f"scb_{entity}_silver", source=source, destination="silver", env=env
    )
    log = get_logger(f"silver.{entity}", ctx=ctx)
    audit = BatchAudit(
        batch_id=ctx.batch_id, pipeline=ctx.pipeline, source=source, destination="silver"
    )

    try:
        schema = TableSchema.from_dict(entity, entity_cfg["schema"])
        rules = [rule_from_dict(r) for r in entity_cfg.get("dq_rules", [])]

        bronze_path = f"{bronze_root}/{source}/{entity}"
        df = spark.read.parquet(bronze_path)
        rows_read = df.count()

        typed = apply_casts(df, schema)
        deduped = apply_dedup(typed, business_keys, entity_cfg.get("dedup_order_by", "_ingest_ts"))

        clean, quarantine, results = evaluate_spark(deduped, rules, key_column=business_keys[0])

        # persist quarantine for inspection/replay
        q_count = quarantine.count()
        if q_count:
            (
                quarantine.write.mode("append").parquet(
                    f"{quarantine_root}/{entity}/batch_id={ctx.batch_id}"
                )
            )

        from pyspark.sql import functions as F  # local import (Spark-only path)

        if scd == "scd2":
            prepared = (
                add_row_hash(clean.select(*business_keys, *tracked), tracked)
                .withColumn("effective_from", F.current_timestamp())
                .withColumn("effective_to", F.to_timestamp(F.lit("9999-12-31 00:00:00")))
                .withColumn("is_current", F.lit(True))
                .withColumn("batch_id", F.lit(ctx.batch_id))
            )
            sk = entity_cfg["surrogate_key"]
            prepared = add_surrogate_key(prepared, business_keys, sk, version_col="effective_from")
            insert_cols = _ensure_scd2_table(spark, target, sk, business_keys, tracked, schema)
            apply_scd2(
                spark,
                prepared.select(*insert_cols),
                target=target,
                business_keys=business_keys,
                insert_columns=insert_cols,
            )
        else:  # scd1 / upsert (idempotent fact/dim overwrite)
            prepared = clean.withColumn("batch_id", F.lit(ctx.batch_id))
            all_cols = [c.name for c in schema.columns] + ["batch_id"]
            col_types = [(c.name, SPARK_TYPES[c.dtype]) for c in schema.columns] + [
                ("batch_id", "string")
            ]
            spark.sql(build_create_iceberg_table(target, col_types))
            update_cols = [c for c in all_cols if c not in business_keys]
            apply_scd1(
                spark,
                prepared.select(*all_cols),
                target=target,
                business_keys=business_keys,
                update_columns=update_cols,
                insert_columns=all_cols,
            )

        rows_written = spark.table(target).count() if scd != "scd2" else clean.count()
        audit.rows_read = rows_read
        audit.rows_written = rows_written
        audit.rows_rejected = q_count
        finalize(audit, status="success")

        metastore.write_dq(
            [
                DQResultRecord(
                    batch_id=ctx.batch_id,
                    entity=entity,
                    rule=r.rule,
                    severity=r.severity,
                    passed=r.passed,
                    failed=r.failed,
                    threshold=r.threshold,
                    breached=r.breached,
                )
                for r in results
            ]
        )
        metastore.write_batch(audit)
        log.metrics(
            status="success",
            rows_read=rows_read,
            rows_written=rows_written,
            rows_rejected=q_count,
            duration_s=audit.duration_s,
        )

        # enforce error-severity thresholds after auditing
        DQReport(results=results).raise_if_failed()
    except Exception as exc:
        finalize(audit, status="failed", error=str(exc))
        metastore.write_batch(audit)
        log.error("silver_failed", exc_info=True, error=str(exc))
        raise


def main(argv: list[str] | None = None) -> int:
    from scb_common.config import load_config
    from spark.transforms.session import build_spark

    ap = argparse.ArgumentParser(description="Bronze -> Silver (Iceberg).")
    ap.add_argument("--entity", required=True)
    ap.add_argument("--config-dir", default="config/silver")
    ap.add_argument("--bronze-root", default="data/bronze")
    ap.add_argument("--quarantine-root", default="data/quarantine")
    ap.add_argument("--audit-dir", default="data/_audit")
    ap.add_argument("--catalog", default="scb")
    ap.add_argument("--warehouse", default="data/silver/iceberg")
    args = ap.parse_args(argv)

    cfg = load_config(Path(args.config_dir) / f"{args.entity}.yaml")
    spark = build_spark(
        app_name=f"scb-silver-{args.entity}", catalog=args.catalog, warehouse=args.warehouse
    )
    try:
        run_silver(
            spark,
            cfg,
            bronze_root=args.bronze_root,
            catalog=args.catalog,
            metastore=JsonlMetadataStore(args.audit_dir),
            quarantine_root=args.quarantine_root,
        )
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
