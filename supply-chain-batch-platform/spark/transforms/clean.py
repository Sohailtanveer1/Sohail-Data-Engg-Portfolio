"""Spark appliers for typing and deduplication (compile-checked; run on JDK/Dataproc)."""

from __future__ import annotations

from scb_common.schema import TableSchema
from spark.transforms.expressions import (
    cast_select_exprs,
    dedup_row_number_expr,
    row_hash_expr,
    surrogate_key_expr,
)


def apply_casts(df, schema: TableSchema):
    """Cast Bronze string columns to their Silver types (empty string -> null)."""
    return df.selectExpr(*cast_select_exprs(schema))


def apply_dedup(df, business_keys: list[str], order_by: str, descending: bool = True):
    """Keep one row per business key (latest by ``order_by``)."""
    from pyspark.sql import functions as F

    rn = dedup_row_number_expr(business_keys, order_by, descending)
    return (
        df.withColumn("_rn", F.expr(rn))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )


def add_row_hash(df, tracked_columns: list[str], name: str = "row_hash"):
    from pyspark.sql import functions as F

    return df.withColumn(name, F.expr(row_hash_expr(tracked_columns)))


def add_surrogate_key(df, business_keys: list[str], name: str,
                      version_col: str | None = None):
    from pyspark.sql import functions as F

    return df.withColumn(name, F.expr(surrogate_key_expr(business_keys, version_col)))
