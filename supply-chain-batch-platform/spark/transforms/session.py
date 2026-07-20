"""SparkSession factory with Iceberg + Spark-tuning defaults.

Works two places unchanged:
- **local** (JDK + pyspark): a Hadoop/GCS-backed Iceberg catalog under a local
  warehouse dir; downloads the Iceberg runtime jar via `spark.jars.packages`.
- **Dataproc Serverless**: the Iceberg jar is provided on the batch, and the
  catalog points at a GCS warehouse; this factory just sets the SQL extensions.

Tuning defaults reflect the Phase-6 topics: AQE (skew + coalesce), dynamic
partition overwrite (idempotent writes), and sensible shuffle partitions.
"""

from __future__ import annotations

import os

ICEBERG_PACKAGE = "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1"


def build_spark(
    app_name: str = "scb-silver",
    *,
    catalog: str = "scb",
    warehouse: str | None = None,
    with_packages: bool = True,
):
    """Return a configured SparkSession. Import is local so this module is
    importable without pyspark (for compile checks/tests of the builders)."""
    from pyspark.sql import SparkSession

    warehouse = warehouse or os.environ.get("SCB_ICEBERG_WAREHOUSE", "spark-warehouse/iceberg")

    builder = (
        SparkSession.builder.appName(app_name)
        # --- Iceberg catalog (ADR-0004) ---
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config(f"spark.sql.catalog.{catalog}", "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{catalog}.type", "hadoop")
        .config(f"spark.sql.catalog.{catalog}.warehouse", warehouse)
        # --- Spark tuning (Phase-6 topics) ---
        .config("spark.sql.adaptive.enabled", "true")  # AQE
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")  # small-file fix
        .config("spark.sql.adaptive.skewJoin.enabled", "true")  # skew handling
        .config("spark.sql.shuffle.partitions", "200")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")  # idempotent writes
        .config("spark.sql.autoBroadcastJoinThreshold", str(64 * 1024 * 1024))  # broadcast dims
    )
    if with_packages:
        builder = builder.config("spark.jars.packages", ICEBERG_PACKAGE)
    return builder.getOrCreate()
