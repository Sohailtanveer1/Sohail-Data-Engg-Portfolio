"""Unit tests for the pure Spark-SQL builders (no SparkSession needed)."""

from scb_common.dq import (
    AllowedValues,
    NonNegative,
    NotNull,
    Unique,
    ValidDate,
)
from scb_common.schema import ColumnSpec, TableSchema
from spark.transforms.expressions import (
    build_create_iceberg_table,
    cast_select_exprs,
    dedup_row_number_expr,
    rule_to_condition,
    row_hash_expr,
    surrogate_key_expr,
)

SCHEMA = TableSchema(
    entity="po",
    columns=[
        ColumnSpec("po_number", "string", nullable=False),
        ColumnSpec("order_qty", "int"),
        ColumnSpec("order_date", "date"),
    ],
)


def test_cast_select_exprs_types_and_null_handling():
    exprs = cast_select_exprs(SCHEMA)
    assert "CAST(NULLIF(`po_number`, '') AS string) AS `po_number`" in exprs
    assert "CAST(NULLIF(`order_qty`, '') AS int) AS `order_qty`" in exprs
    assert "to_date(NULLIF(`order_date`, '')) AS `order_date`" in exprs


def test_rule_to_condition_not_null():
    assert rule_to_condition(NotNull("material_id")) == "(`material_id` IS NOT NULL AND `material_id` <> '')"


def test_rule_to_condition_non_negative_allows_null_rejects_text():
    cond = rule_to_condition(NonNegative("order_qty"))
    assert "`order_qty` IS NULL" in cond
    assert "CAST(`order_qty` AS DOUBLE) >= 0" in cond
    assert "IS NOT NULL" in cond  # non-numeric text fails


def test_rule_to_condition_allowed_values_quotes_and_sorts():
    cond = rule_to_condition(AllowedValues("currency", allowed={"USD", "CAD"}))
    assert cond == "(`currency` IS NULL OR `currency` IN ('CAD', 'USD'))"


def test_rule_to_condition_valid_date():
    assert rule_to_condition(ValidDate("order_date")) == "(`order_date` IS NULL OR to_date(`order_date`) IS NOT NULL)"


def test_unique_and_fk_return_none():
    assert rule_to_condition(Unique("po_number")) is None


def test_row_hash_and_surrogate_are_deterministic_sha256():
    h = row_hash_expr(["a", "b"])
    assert h == "sha2(concat_ws('||', coalesce(cast(`a` as string), ''), coalesce(cast(`b` as string), '')), 256)"
    sk = surrogate_key_expr(["material_id"], version_col="effective_from")
    assert "effective_from" in sk and sk.startswith("sha2(")


def test_dedup_window_expr():
    e = dedup_row_number_expr(["po_number", "po_line"], "_ingest_ts")
    assert e == "row_number() OVER (PARTITION BY `po_number`, `po_line` ORDER BY `_ingest_ts` DESC)"


def test_create_iceberg_table_ddl():
    ddl = build_create_iceberg_table("scb.silver.x", [("id", "string"), ("v", "int")],
                                     partition_by=["id"])
    assert ddl == ("CREATE TABLE IF NOT EXISTS scb.silver.x (`id` string, `v` int) "
                   "USING iceberg PARTITIONED BY (`id`)")
