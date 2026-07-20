"""Slowly Changing Dimension builders + appliers (Iceberg MERGE INTO).

The SQL builders are **pure** (unit-tested without Spark). The `apply_*` functions
execute them via ``spark.sql`` against Iceberg tables (ADR-0004, ADR-0006).

SCD2 is the classic two-step:
  1. MERGE to *close* the currently-open row when the tracked attributes changed.
  2. INSERT the new/changed versions (open, is_current=true).
Idempotent: re-running with the same source is a no-op (row_hash matches).
"""

from __future__ import annotations


def _on(business_keys: list[str], left: str = "t", right: str = "s") -> str:
    return " AND ".join(f"{left}.`{k}` = {right}.`{k}`" for k in business_keys)


def build_scd1_merge_sql(target: str, source: str, business_keys: list[str],
                         update_columns: list[str], insert_columns: list[str]) -> str:
    """SCD1 (overwrite): update matched rows in place, insert new ones."""
    set_clause = ", ".join(f"t.`{c}` = s.`{c}`" for c in update_columns)
    insert_cols = ", ".join(f"`{c}`" for c in insert_columns)
    insert_vals = ", ".join(f"s.`{c}`" for c in insert_columns)
    return (
        f"MERGE INTO {target} t\n"
        f"USING {source} s\n"
        f"ON {_on(business_keys)}\n"
        f"WHEN MATCHED THEN UPDATE SET {set_clause}\n"
        f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})"
    )


def build_scd2_close_sql(target: str, source: str, business_keys: list[str]) -> str:
    """Step 1: close the open row when tracked attributes (row_hash) changed."""
    return (
        f"MERGE INTO {target} t\n"
        f"USING {source} s\n"
        f"ON {_on(business_keys)} AND t.`is_current` = true\n"
        f"WHEN MATCHED AND t.`row_hash` <> s.`row_hash` THEN\n"
        f"  UPDATE SET t.`is_current` = false, t.`effective_to` = s.`effective_from`"
    )


def build_scd2_insert_sql(target: str, source: str, business_keys: list[str],
                          insert_columns: list[str]) -> str:
    """Step 2: insert brand-new keys and changed versions (open rows)."""
    cols = ", ".join(f"`{c}`" for c in insert_columns)
    select = ", ".join(f"s.`{c}`" for c in insert_columns)
    first_key = business_keys[0]
    return (
        f"INSERT INTO {target} ({cols})\n"
        f"SELECT {select}\n"
        f"FROM {source} s\n"
        f"LEFT JOIN {target} t ON {_on(business_keys)} AND t.`is_current` = true\n"
        f"WHERE t.`{first_key}` IS NULL OR t.`row_hash` <> s.`row_hash`"
    )


def build_scd2_statements(target: str, source: str, business_keys: list[str],
                          insert_columns: list[str]) -> list[str]:
    """The full SCD2 sequence: close-then-insert (run in order)."""
    return [
        build_scd2_close_sql(target, source, business_keys),
        build_scd2_insert_sql(target, source, business_keys, insert_columns),
    ]


# ---- Spark appliers (require a SparkSession; compile-checked, run on JDK/Dataproc) ----

def apply_scd1(spark, df, *, target: str, business_keys: list[str],
               update_columns: list[str], insert_columns: list[str]) -> None:
    view = "scd1_src"
    df.createOrReplaceTempView(view)
    spark.sql(build_scd1_merge_sql(target, view, business_keys, update_columns, insert_columns))


def apply_scd2(spark, df, *, target: str, business_keys: list[str],
               insert_columns: list[str]) -> None:
    view = "scd2_src"
    df.createOrReplaceTempView(view)
    for stmt in build_scd2_statements(target, view, business_keys, insert_columns):
        spark.sql(stmt)
