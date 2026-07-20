"""Silver -> Gold Spark job: assemble the star schema and load it to BigQuery.

Facts read from Silver (Iceberg), resolve conformed-dimension surrogate keys via
point-in-time joins, compute measures, and write to the partitioned BigQuery Gold
tables from Phase 4 using the Spark-BigQuery connector.

Config-driven (config/gold/<entity>.yaml). Compile-checked here; executed on a
JDK/Dataproc with the BigQuery + Iceberg jars (see docs/phase-07).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scb_common.context import BatchContext
from scb_common.logging import get_logger
from scb_common.metadata import BatchAudit, JsonlMetadataStore, finalize

from spark.transforms.gold import DimJoin, build_fact_select


def _dims_from_cfg(cfg: dict) -> list[DimJoin]:
    return [
        DimJoin(
            name=d["name"], table=d["table"].replace("scb.", ""),
            business_key=d["business_key"], sk_column=d["sk"],
            scd=d.get("scd", "scd1"), fact_date=d.get("fact_date"),
            dim_key=d.get("dim_key"),
        )
        for d in cfg.get("dimensions", [])
    ]


def build_fact(spark, cfg: dict, *, catalog: str):
    """Return the assembled Gold fact DataFrame (not yet written)."""
    silver_source = cfg["silver_source"].replace("scb.", f"{catalog}.")
    sql = build_fact_select(
        silver_source,
        surrogate_name=cfg["surrogate_key"]["name"],
        surrogate_keys=cfg["surrogate_key"]["keys"],
        date_column=cfg["date_column"],
        dims=[DimJoin(**{**d.__dict__, "table": d.table.replace("scb.", f"{catalog}.")})
              for d in _dims_from_cfg(cfg)],
        measures=cfg.get("measures", []),
    )
    return spark.sql(sql)


def write_bigquery(df, *, table: str, dataset: str, project: str, temp_bucket: str,
                   partition_field: str | None) -> None:
    writer = (df.write.format("bigquery")
              .option("table", f"{project}.{dataset}.{table}")
              .option("temporaryGcsBucket", temp_bucket)
              .mode("overwrite"))
    if partition_field:
        writer = writer.option("partitionField", partition_field).option("partitionType", "DAY")
    writer.save()


def run_gold(spark, cfg: dict, *, catalog: str, project: str, dataset: str,
             temp_bucket: str, metastore, env: str = "local") -> None:
    entity = cfg["entity"]
    ctx = BatchContext(pipeline=f"scb_{entity}_gold", source="silver",
                       destination="gold", env=env)
    log = get_logger(f"gold.{entity}", ctx=ctx)
    audit = BatchAudit(batch_id=ctx.batch_id, pipeline=ctx.pipeline,
                       source="silver", destination="gold")
    try:
        fact = build_fact(spark, cfg, catalog=catalog)
        rows = fact.count()
        write_bigquery(fact, table=cfg["target_table"], dataset=dataset, project=project,
                       temp_bucket=temp_bucket, partition_field=cfg.get("date_column"))
        audit.rows_read = rows
        audit.rows_written = rows
        finalize(audit, status="success")
        metastore.write_batch(audit)
        log.metrics(status="success", rows_read=rows, rows_written=rows,
                    duration_s=audit.duration_s)
    except Exception as exc:  # noqa: BLE001
        finalize(audit, status="failed", error=str(exc))
        metastore.write_batch(audit)
        log.error("gold_failed", exc_info=True, error=str(exc))
        raise


def main(argv: list[str] | None = None) -> int:
    from scb_common.config import load_config
    from spark.transforms.session import build_spark

    ap = argparse.ArgumentParser(description="Silver -> Gold (BigQuery).")
    ap.add_argument("--entity", required=True)
    ap.add_argument("--config-dir", default="config/gold")
    ap.add_argument("--catalog", default="scb")
    ap.add_argument("--warehouse", default="data/silver/iceberg")
    ap.add_argument("--project", required=True)
    ap.add_argument("--dataset", required=True)          # e.g. scb_gold_dev
    ap.add_argument("--temp-bucket", required=True)      # gs://scb-<proj>-dev-temp
    ap.add_argument("--audit-dir", default="data/_audit")
    args = ap.parse_args(argv)

    cfg = load_config(Path(args.config_dir) / f"{args.entity}.yaml")
    spark = build_spark(app_name=f"scb-gold-{args.entity}", catalog=args.catalog,
                        warehouse=args.warehouse)
    try:
        run_gold(spark, cfg, catalog=args.catalog, project=args.project,
                 dataset=args.dataset, temp_bucket=args.temp_bucket,
                 metastore=JsonlMetadataStore(args.audit_dir))
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
